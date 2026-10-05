import {writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';

// Read-only provider access. Never emit credentials, account identifiers or raw API bodies.
export async function inspectProvider({accountId, apiToken, freeReported, fetcher = fetch}) {
  const report = {
    schema: 'QROS_G12_PROVIDER_PREFLIGHT_V1',
    status: 'BLOCKED',
    provider_access: 'NOT_CHECKED',
    free_plan: freeReported === 'true' ? 'REPORTADO_EXISTING_GITHUB_GATE' : 'NO_DISPONIBLE',
    deployment: 'NOT_ATTEMPTED',
    paid_services_activated: false,
    checks: [],
  };
  if (!/^[0-9a-f]{32}$/.test(accountId || '') || !apiToken) {
    report.reason = 'MISSING_PROVIDER_CONFIGURATION';
    return report;
  }
  async function read(path, label) {
    let response, body;
    try {
      response = await fetcher(`https://api.cloudflare.com/client/v4/accounts/${accountId}/${path}`, {
        headers: {Authorization: `Bearer ${apiToken}`}, redirect: 'error',
        signal: AbortSignal.timeout(15000),
      });
      body = await response.json();
    } catch {
      report.checks.push({name: label, status: 'NETWORK_OR_FORMAT_FAILURE'});
      return null;
    }
    const codes = Array.isArray(body.errors) ? body.errors.map(e => e.code).filter(Number.isInteger) : [];
    report.checks.push({name: label, http_status: response.status, success: response.ok && body.success === true, error_codes: codes});
    return response.ok && body.success === true ? body.result : null;
  }
  const subdomain = await read('workers/subdomain', 'account_workers_access');
  if (!subdomain || !/^[a-z0-9][a-z0-9-]{0,62}$/.test(subdomain.subdomain || '')) {
    report.reason = 'PROVIDER_ACCESS_NOT_ESTABLISHED';
    return report;
  }
  report.provider_access = 'VERIFICADO';
  report.public_origin = `https://qros-mobile-g12-test-only.${subdomain.subdomain}.workers.dev`;
  const settings = await read('workers/account-settings', 'worker_settings');
  if (settings && typeof settings.default_usage_model === 'string') {
    // This field describes a usage model, not proof of the account's subscription.
    report.worker_usage_model = ['standard', 'bundled', 'unbound'].includes(settings.default_usage_model)
      ? settings.default_usage_model : 'OTHER';
  }
  const existing = await read('workers/scripts/qros-mobile-g12-test-only/settings', 'existing_g12');
  report.existing_g12 = existing ? 'PRESENT' : 'NOT_ESTABLISHED';
  report.status = 'ACCESS_READY_DEPLOYMENT_GATED';
  report.reason = freeReported === 'true'
    ? 'FREE_PLAN_CURRENT_CONFIRMATION_AND_REVIEWABLE_DEPLOYMENT_REQUIRED'
    : 'FREE_PLAN_CONFIRMATION_REQUIRED';
  return report;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const report = await inspectProvider({
    accountId: process.env.CLOUDFLARE_ACCOUNT_ID,
    apiToken: process.env.CLOUDFLARE_API_TOKEN,
    freeReported: process.env.QROS_FREE_PLAN_REPORTED,
  });
  report.source_commit = process.env.GITHUB_SHA || 'LOCAL_TEST_ONLY';
  report.checked_at = new Date().toISOString();
  await writeFile(process.argv[2] || '/tmp/qros-g12-provider-preflight.json', JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report));
  if (report.provider_access !== 'VERIFICADO') process.exitCode = 1;
}
