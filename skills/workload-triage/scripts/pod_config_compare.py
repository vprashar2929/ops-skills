#!/usr/bin/env python3
"""Compare config wiring in one Deployment, its ReplicaSet and an owned Pod."""

import argparse
import json
import sys


class InputError(ValueError):
    pass


def fields(obj, names):
    """Allow only scalar fields; never copy arbitrary nested input into output."""
    result = {}
    for name in names:
        if name in obj:
            value = obj[name]
            if value is not None and not isinstance(value, (str, bool, int)):
                raise InputError("Expected scalar reference metadata")
            if isinstance(value, str) and len(value) > 4096:
                raise InputError("Reference metadata exceeds the supported size")
            result[name] = value
    return result


def named(items):
    result = {}
    for item in items:
        name = fields(item, ("name",)).get("name")
        if not isinstance(name, str) or not name or name in result:
            raise InputError("Expected unique named entries")
        result[name] = item
    return result


def reference(obj):
    return {**fields(obj, ("name", "key")), "optional": boolean(obj, "optional", False)}


def boolean(obj, key, default=None):
    value = obj.get(key, default)
    if value is not None and not isinstance(value, bool):
        raise InputError("Expected boolean reference metadata")
    return value


def value_from(obj):
    result = {}
    for kind in ("secretKeyRef", "configMapKeyRef"):
        if kind in obj:
            result[kind] = reference(obj[kind])
    if "fieldRef" in obj:
        result["fieldRef"] = {"apiVersion": "v1", **fields(obj["fieldRef"], ("apiVersion", "fieldPath"))}
    if "resourceFieldRef" in obj:
        result["resourceFieldRef"] = fields(obj["resourceFieldRef"], ("containerName", "resource", "divisor"))
    result["unprojectedKinds"] = sorted(set(obj) - set(result))
    return result


def config_source(kind, obj):
    if kind in ("secret", "configMap"):
        result = {**fields(obj, ("name", "secretName")), "optional": boolean(obj, "optional", False)}
        result["items"] = [fields(item, ("key", "path", "mode")) for item in obj.get("items", [])]
        return result
    if kind == "serviceAccountToken":
        return fields(obj, ("path", "audience", "expirationSeconds"))
    if kind == "downwardAPI":
        return {"items": [{**fields(item, ("path", "mode")), **value_from(
            {key: item[key] for key in ("fieldRef", "resourceFieldRef") if key in item})}
            for item in obj.get("items", [])]}
    if kind == "csi":
        return {**fields(obj, ("driver", "readOnly")),
                "nodePublishSecretRef": fields(obj.get("nodePublishSecretRef") or {}, ("name",)),
                "volumeAttributes": fields(obj.get("volumeAttributes") or {}, ("secretProviderClass",))}
    return {"detailsNotCompared": True}


def project(spec):
    result = {"serviceAccountName": fields(spec, ("serviceAccountName",)).get("serviceAccountName") or "default",
              "automountServiceAccountToken": boolean(spec, "automountServiceAccountToken"),
              "imagePullSecrets": sorted(named(spec.get("imagePullSecrets", []))), "volumes": {}}
    for category in ("containers", "initContainers", "ephemeralContainers"):
        result[category] = {}
        for name, container in named(spec.get(category, [])).items():
            env = []
            for entry in container.get("env", []):
                env.append({**fields(entry, ("name",)),
                            "source": value_from(entry["valueFrom"]) if "valueFrom" in entry
                            else {"literalValueNotCompared": True}})
            imports = []
            for entry in container.get("envFrom", []):
                imports.append({"prefix": "", **fields(entry, ("prefix",)),
                                **{kind: reference(entry[kind]) for kind in ("secretRef", "configMapRef")
                                   if kind in entry}})
            result[category][name] = {"present": True, "env": env, "envFrom": imports,
                **fields(container, ("restartPolicy",)),
                "volumeMounts": [fields(mount, ("name", "mountPath", "readOnly", "subPath", "subPathExpr"))
                                 for mount in container.get("volumeMounts", [])]}
    for name, volume in named(spec.get("volumes", [])).items():
        result["volumes"][name] = {}
        for kind, source in volume.items():
            if kind == "name":
                continue
            if kind == "projected":
                projected = [{k: config_source(k, v) for k, v in item.items()}
                             for item in source.get("sources", [])]
                result["volumes"][name][kind] = {"present": True, "sources": projected}
            else:
                result["volumes"][name][kind] = config_source(kind, source)
    return result


def flatten(obj, path=""):
    """JSON Pointer leaf paths preserve env/import order and expose no raw objects."""
    if isinstance(obj, dict):
        pairs = obj.items()
    elif isinstance(obj, list):
        pairs = enumerate(obj)
    else:
        if obj is not None and not isinstance(obj, (str, int, bool)):
            raise InputError("Expected scalar projected data")
        if isinstance(obj, str) and len(obj) > 4096:
            raise InputError("Projected data exceeds the supported size")
        return {path: obj}
    result = {}
    for key, value in pairs:
        key = str(key).replace("~", "~0").replace("/", "~1")
        result.update(flatten(value, path + "/" + key))
    return result


def diff(before, after, offset, limit):
    before, after = flatten(before), flatten(after)
    changes = []
    for path in sorted(set(before) | set(after)):
        if path not in before:
            changes.append({"path": path, "change": "added", "after": after[path]})
        elif path not in after:
            changes.append({"path": path, "change": "removed", "before": before[path]})
        elif before[path] != after[path]:
            changes.append({"path": path, "change": "changed", "before": before[path], "after": after[path]})
    page = changes[offset:offset + limit]
    return {"count": len(changes), "offset": offset, "changes": page,
            "remaining": max(0, len(changes) - offset - len(page))}


def owned_by(child, parent):
    owners = [o for o in child["metadata"].get("ownerReferences", []) if o.get("controller") is True]
    if len(owners) != 1 or any(owners[0].get(k) != parent[k] for k in ("apiVersion", "kind")) or any(
            owners[0].get(k) != parent["metadata"][k] for k in ("name", "uid")):
        raise InputError("Controller owner name/UID/API does not match the supplied parent")


def coverage_gaps(config, offset, limit):
    paths = set()
    for path, value in flatten(config).items():
        if path.endswith('/detailsNotCompared') and value is True:
            paths.add(path.rsplit('/', 1)[0])
        elif '/unprojectedKinds/' in path:
            paths.add(path.split('/unprojectedKinds/')[0] + '/' + value.replace('~', '~0').replace('/', '~1'))
    paths = sorted(paths)
    page = paths[offset:offset + limit]
    return {'count': len(paths), 'offset': offset, 'paths': page,
            'remaining': max(0, len(paths) - offset - len(page))}


def compare(document, offset=0, limit=50):
    if document.get("kind") != "List" or len(document.get("items", [])) != 3:
        raise InputError("Supply exactly one Deployment, ReplicaSet and Pod in a Kubernetes List")
    objects = {o["kind"]: o for o in document["items"]}
    if set(objects) != {"Deployment", "ReplicaSet", "Pod"}:
        raise InputError("Supply exactly one Deployment, ReplicaSet and Pod")
    for kind, obj in objects.items():
        if obj["apiVersion"] != ("v1" if kind == "Pod" else "apps/v1"):
            raise InputError("Unsupported API version")
        for field in ("name", "namespace", "uid", "resourceVersion"):
            if not isinstance(obj["metadata"].get(field), str) or not obj["metadata"][field]:
                raise InputError("Object identity metadata is missing")
    deployment, rs, pod = (objects[k] for k in ("Deployment", "ReplicaSet", "Pod"))
    if len({o["metadata"]["namespace"] for o in objects.values()}) != 1:
        raise InputError("Objects must share a namespace")
    owned_by(rs, deployment)
    owned_by(pod, rs)
    configs = [project(o["spec"]["template"]["spec"]) for o in (deployment, rs)] + [project(pod["spec"])]
    observed = []
    for kind in ("Deployment", "ReplicaSet", "Pod"):
        obj = objects[kind]
        observed.append({"kind": kind, **fields(obj["metadata"],
                         ("name", "namespace", "uid", "resourceVersion", "generation", "creationTimestamp", "deletionTimestamp")),
                         "revision": fields(obj["metadata"].get("annotations", {}),
                                            ("deployment.kubernetes.io/revision",)).get("deployment.kubernetes.io/revision")})
    return {"ownershipVerified": True, "objects": observed,
            "podPhase": fields(pod.get("status", {}), ("phase", "startTime")),
            "deploymentToReplicaSet": diff(configs[0], configs[1], offset, limit),
            "replicaSetToPod": diff(configs[1], configs[2], offset, limit),
            "coverageGaps": {name: coverage_gaps(config, offset, limit)
                             for name, config in zip(('deployment', 'replicaSet', 'pod'), configs)},
            "limits": "One Pod snapshot; config references only. Literal values, commands, arguments, "
                      "annotations, images, resource limits and process state are not compared. "
                      "Differences do not establish a mutating webhook or other cause."}


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog=
        "Example: kubectl ... get deployment/APP replicaset/RS pod/POD -o json | "
        "python3 pod_config_compare.py\nUse pipefail to retain collection failures. "
        "Exit 0: comparison completed; 1: input/ownership error; 2: invalid arguments.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offset", type=int, default=0, help="Change offset in each comparison (default 0)")
    parser.add_argument("--limit", type=int, default=50, help="Changes per comparison, 1–200 (default 50)")
    args = parser.parse_args()
    if args.offset < 0 or not 1 <= args.limit <= 200:
        parser.error("offset must be nonnegative and limit must be 1–200")
    try:
        result = compare(json.load(sys.stdin), args.offset, args.limit)
    except InputError as error:
        print(f"Comparison failed: {error}. Raw input omitted.", file=sys.stderr)
        return 1
    except (ValueError, KeyError, TypeError, AttributeError):
        print("Comparison failed: invalid object structure/JSON; check collection exit status. Raw input omitted.", file=sys.stderr)
        return 1
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
