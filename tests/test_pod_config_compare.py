"""Owner-safe config comparisons and payload exclusion without cluster access."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

HELPER = Path(__file__).resolve().parents[1] / 'skills/workload-triage/scripts/pod_config_compare.py'
spec = importlib.util.spec_from_file_location('pod_config_compare', HELPER)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CANARY = 'SYNTHETIC_SECRET_VALUE_NEVER_EMIT'


def fixture():
    config = {'containers': [{'name': 'app', 'env': [{'name': 'PASSWORD', 'value': CANARY}],
        'envFrom': [{'secretRef': {'name': 'app-secret'}}], 'args': [CANARY]}]}
    def obj(kind, name, uid, config, parent=None):
        meta = {'name': name, 'uid': uid, 'namespace': 'demo', 'resourceVersion': '42',
                'annotations': {'arbitrary': CANARY}}
        if parent:
            meta['ownerReferences'] = [{'apiVersion': 'apps/v1', 'kind': parent['kind'],
                'name': parent['metadata']['name'], 'uid': parent['metadata']['uid'], 'controller': True}]
        return {'apiVersion': 'v1' if kind == 'Pod' else 'apps/v1', 'kind': kind,
                'metadata': meta, 'spec': copy.deepcopy(config if kind == 'Pod' else {'template': {'spec': config}})}
    dep = obj('Deployment', 'app', 'dep-1', config)
    rs = obj('ReplicaSet', 'app-abc', 'rs-1', config, dep)
    pod = obj('Pod', 'app-abc-one', 'pod-1', config, rs)
    return {'kind': 'List', 'items': [dep, rs, pod]}


class PodConfigTests(unittest.TestCase):
    def run_helper(self, document, *args):
        return subprocess.run([sys.executable, str(HELPER), *args], input=json.dumps(document),
                              text=True, capture_output=True, timeout=5)

    def test_equal_wiring_and_values_excluded(self):
        doc = fixture()
        doc['items'][2]['spec']['containers'][0]['env'][0]['value'] = 'DIFFERENT_' + CANARY
        result = self.run_helper(doc)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(CANARY, result.stdout + result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output['ownershipVerified'])
        self.assertEqual(output['replicaSetToPod']['count'], 0)
        self.assertIn('Literal values', output['limits'])

    def test_added_native_sidecar_and_projected_volumes(self):
        doc = fixture()
        pod = doc['items'][2]['spec']
        pod['initContainers'] = [{'name': 'proxy', 'restartPolicy': 'Always', 'args': [CANARY],
                                 'volumeMounts': [{'name': 'token', 'mountPath': '/tokens', 'readOnly': True}]}]
        pod['volumes'] = [{'name': 'token', 'projected': {'sources': [
            {'serviceAccountToken': {'path': 'token', 'audience': 'mesh'}},
            {'configMap': {'name': 'mesh-ca', 'items': [{'key': 'root', 'path': 'ca'}]}},
            {'downwardAPI': {'items': [{'path': 'labels', 'fieldRef': {'fieldPath': 'metadata.labels'}}]}}]}},
            {'name': 'external', 'csi': {'driver': 'secrets-store.csi.k8s.io',
             'volumeAttributes': {'secretProviderClass': 'provider', 'sensitive': CANARY},
             'nodePublishSecretRef': {'name': 'auth'}}}]
        result = self.run_helper(doc)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(CANARY, result.stdout + result.stderr)
        changes = json.loads(result.stdout)['replicaSetToPod']['changes']
        self.assertIn({'path': '/initContainers/proxy/restartPolicy', 'change': 'added', 'after': 'Always'}, changes)
        self.assertTrue(any(c.get('after') == 'mesh-ca' for c in changes))
        self.assertTrue(any(c.get('after') == 'provider' for c in changes))

    def test_rollout_differences_are_separate(self):
        doc = fixture()
        doc['items'][0]['spec']['template']['spec']['containers'][0]['envFrom'][0]['secretRef']['name'] = 'new-secret'
        result = module.compare(doc)
        self.assertEqual(result['deploymentToReplicaSet']['count'], 1)
        self.assertEqual(result['replicaSetToPod']['count'], 0)

    def test_reject_wrong_owner_namespace_and_missing_identity(self):
        for mutation in ('uid', 'namespace', 'controller', 'missing', 'api'):
            doc = fixture()
            pod = doc['items'][2]
            if mutation == 'uid': pod['metadata']['ownerReferences'][0]['uid'] = 'recreated-rs'
            if mutation == 'namespace': pod['metadata']['namespace'] = 'other'
            if mutation == 'controller': pod['metadata']['ownerReferences'][0]['controller'] = False
            if mutation == 'missing': del pod['metadata']['uid']
            if mutation == 'api': pod['metadata']['ownerReferences'][0]['apiVersion'] = 'wrong/v1'
            result = self.run_helper(doc)
            self.assertNotEqual(result.returncode, 0, mutation)
            self.assertEqual(result.stdout, '')
            self.assertNotIn(CANARY, result.stderr)

    def test_ordered_imports_optional_flags_and_subpath_changes(self):
        doc = fixture()
        container = doc['items'][2]['spec']['containers'][0]
        container['envFrom'][0]['secretRef']['optional'] = True
        container['envFrom'].append({'prefix': 'OTHER_', 'configMapRef': {'name': 'options'}})
        container['volumeMounts'] = [{'name': 'config', 'mountPath': '/config', 'subPath': 'app.yaml'}]
        result = module.compare(doc)['replicaSetToPod']
        self.assertTrue(any(c['path'].endswith('/optional') and c.get('after') is True for c in result['changes']))
        self.assertTrue(any(c['path'].endswith('/subPath') for c in result['changes']))

    def test_pagination_counts_all_changes(self):
        doc = fixture()
        doc['items'][2]['spec']['containers'][0]['env'] += [{'name': f'KEY_{i}', 'value': CANARY} for i in range(100)]
        first = module.compare(doc, 0, 20)['replicaSetToPod']
        second = module.compare(doc, 20, 20)['replicaSetToPod']
        self.assertEqual(first['count'], 200)
        self.assertEqual(first['remaining'], 180)
        self.assertEqual(second['remaining'], 160)
        self.assertFalse(set(c['path'] for c in first['changes']) & set(c['path'] for c in second['changes']))

    def test_unsupported_sources_stay_visible_when_differences_are_zero(self):
        doc = fixture()
        for obj in doc['items']:
            config = obj['spec'] if obj['kind'] == 'Pod' else obj['spec']['template']['spec']
            config['volumes'] = [{'name': 'legacy', 'flexVolume': {
                'driver': 'example', 'secretRef': {'name': obj['kind'] + '-auth'}, 'options': {'secret': CANARY}}},
                {'name': 'trust', 'projected': {'sources': [{'clusterTrustBundle': {'name': 'roots', 'path': 'ca'}}]}}]
        result = self.run_helper(doc)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(CANARY, result.stdout + result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary['deploymentToReplicaSet']['count'], 0)
        for gaps in summary['coverageGaps'].values():
            self.assertEqual(gaps['count'], 2)
            self.assertIn('/volumes/legacy/flexVolume', gaps['paths'])
            self.assertIn('/volumes/trust/projected/sources/0/clusterTrustBundle', gaps['paths'])

    def test_invalid_input_no_payload_echo(self):
        for doc in (None, {}, {'kind': 'List', 'items': []}, {'kind': 'Secret', 'data': {'a': CANARY}}):
            result = self.run_helper(doc)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertNotIn(CANARY, result.stderr)
        doc = fixture()
        doc['items'][2]['spec']['containers'][0]['envFrom'][0]['prefix'] = {'bad': CANARY}
        self.assertNotIn(CANARY, self.run_helper(doc).stderr)
        self.assertNotEqual(self.run_helper(doc).returncode, 0)


if __name__ == '__main__':
    unittest.main()
