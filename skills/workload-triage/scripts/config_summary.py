#!/usr/bin/env python3
"""Summarize named Kubernetes config objects from stdin without emitting values."""

import argparse
from collections import Counter
import json
import sys


def sample(values):
    names = sorted(set(values))
    return {"count": len(names), "names": names[:20], "omitted": max(0, len(names) - 20)}


def pick(obj, fields):
    return {field: obj[field] for field in fields if field in obj}


def store_ref(ref):
    return pick(ref or {}, ("name", "kind", "namespace"))


def identity(obj):
    return {"kind": obj["kind"], **pick(obj["metadata"],
            ("name", "namespace", "uid", "resourceVersion"))}


def key_names(obj):
    keys = set()
    fields = ("data", "stringData") if obj["kind"] == "Secret" else ("data", "binaryData")
    for field in fields:
        data = obj.get(field)
        if data is None:
            continue
        if not isinstance(data, dict):
            raise ValueError("Key data must be an object")
        keys.update(data)
    return keys


def summarize(document, key=None):
    objects = document.get("items") if document.get("kind") == "List" else [document]
    if not isinstance(objects, list) or not 1 <= len(objects) <= 20:
        raise ValueError("Expected 1–20 named objects; narrow the query")
    # Validate all kinds before generating output; never echo rejected input.
    for obj in objects:
        kind = obj["kind"]
        api = obj["apiVersion"]
        valid = ((kind in ("Secret", "ConfigMap") and api == "v1") or
                 (kind == "ExternalSecret" and api.startswith("external-secrets.io/")))
        if not valid or not obj["metadata"]["name"]:
            raise ValueError("Unsupported resource; expected Secret, ConfigMap or ExternalSecret")
    results = []
    for obj in objects:
        result = identity(obj)
        if obj["kind"] in ("Secret", "ConfigMap"):
            keys = key_names(obj)
            result["keys"] = sample(keys)
            result["owners"] = [pick(owner, ("apiVersion", "kind", "name", "uid", "controller"))
                                for owner in obj["metadata"].get("ownerReferences", [])]
            if key is not None:
                result["requestedKey"] = {"name": key, "present": key in keys}
        else:
            spec = obj.get("spec") or {}
            status = obj.get("status") or {}
            target = spec.get("target") or {}
            data = spec.get("data") or []
            output_keys = {entry["secretKey"] for entry in data}
            target_name = target.get("name") or obj["metadata"]["name"]
            default_store = store_ref(spec.get("secretStoreRef"))
            result.update({
                "target": {"name": target_name, **pick(target, ("creationPolicy", "deletionPolicy"))},
                "store": default_store,
                "explicitKeys": sample(output_keys),
                "dataFromCount": len(spec.get("dataFrom") or []),
                "targetTemplatePresent": bool(target.get("template")),
                **pick(spec, ("refreshPolicy", "refreshInterval")),
                **pick(status, ("refreshTime",)),
                "conditions": [pick(condition, ("type", "status", "reason", "lastTransitionTime"))
                               for condition in status.get("conditions", [])],
            })
            # Count store overrides, retaining kind/name distinctions; omit remote payloads.
            stores = Counter()
            generator_count = 0
            for entry in data:
                source = entry.get("sourceRef") or {}
                if source.get("generatorRef"):
                    generator_count += 1
                else:
                    ref = store_ref(source.get("storeRef")) or default_store
                    stores[json.dumps(ref, sort_keys=True)] += 1
            store_entries = [
                {"store": json.loads(ref), "keyCount": count}
                for ref, count in sorted(stores.items())]
            result["explicitKeyStores"] = {"count": len(store_entries), "entries": store_entries[:20],
                                           "omitted": max(0, len(store_entries) - 20)}
            result["generatorKeyCount"] = generator_count
            if key is not None:
                matches = [entry for entry in data if entry["secretKey"] == key]
                result["requestedKey"] = {"name": key, "explicitMappings": [
                    {"remoteRef": {"version": None, **pick(entry.get("remoteRef") or {},
                                                          ("key", "property", "version"))},
                     "store": store_ref((entry.get("sourceRef") or {}).get("storeRef")) or default_store,
                     "generatorRef": pick((entry.get("sourceRef") or {}).get("generatorRef") or {},
                                          ("apiVersion", "kind", "name"))}
                    for entry in matches]}
            secrets = [candidate for candidate in objects if candidate["kind"] == "Secret"
                       and candidate["metadata"]["name"] == target_name
                       and candidate["metadata"].get("namespace") == obj["metadata"].get("namespace")]
            comparison = {"status": "not-collected", "reason": "Matching target Secret not supplied"}
            if spec.get("dataFrom") or target.get("template"):
                comparison = {"status": "indeterminate", "reason": "dataFrom or templating changes the output key set"}
            elif len(secrets) == 1:
                actual = key_names(secrets[0])
                comparison = {"status": "compared", "expectedCount": len(output_keys),
                              "actualCount": len(actual), "missing": sample(output_keys - actual),
                              "extra": sample(actual - output_keys)}
            elif len(secrets) > 1:
                comparison = {"status": "indeterminate", "reason": "Multiple matching target Secrets supplied"}
            result["targetKeyComparison"] = comparison
        results.append(result)
    return {"objects": results, "valuesEmitted": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", help="Include reference metadata/presence for one exact key")
    args = parser.parse_args()
    try:
        result = summarize(json.load(sys.stdin), args.key)
    except (ValueError, KeyError, TypeError, AttributeError):
        print("Configuration summary failed: invalid/unsupported input or more than 20 objects; "
              "check collector exit status and narrow the query. Raw input omitted.", file=sys.stderr)
        return 1
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
