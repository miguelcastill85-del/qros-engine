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
    if (label === 'workers_plan_subscriptions' && (body.result_info?.total_pages > 1 ||
        body.result_info?.total_count > (Array.isArray(body.result) ? body.result.length : 0))) return null;
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
  const subscriptions = await read('subscriptions?per_page=50', 'workers_plan_subscriptions');
  if (Array.isArray(subscriptions) && subscriptions.length < 50) {
    const workers = subscriptions.filter(s => /workers/i.test(String(s.rate_plan?.id || '') + ' ' + String(s.rate_plan?.public_name || '')));
    report.free_plan = workers.length === 0 ? 'NO_WORKERS_PAID_SUBSCRIPTION_VERIFICADO' : 'WORKERS_SUBSCRIPTION_PRESENT_DEPLOYMENT_BLOCKED';
    report.free_plan_inference = workers.length === 0 ? 'FREE_BY_PROVIDER_DEFAULT' : 'NONE';
  } else {
    report.free_plan_current = 'NO_DISPONIBLE';
  }
  const existing = await read('workers/scripts/qros-mobile-g12-test-only/settings', 'existing_g12');
  report.existing_g12 = existing ? 'PRESENT' : 'NOT_ESTABLISHED';
  report.status = freeReported === 'true' && report.free_plan === 'NO_WORKERS_PAID_SUBSCRIPTION_VERIFICADO'
    ? 'READY_FOR_REVIEWED_FREE_DEPLOYMENT' : 'ACCESS_READY_DEPLOYMENT_GATED';
  report.reason = freeReported === 'true'
    ? 'CURRENT_FREE_PLAN_EVIDENCE_REQUIRED_BEFORE_DEPLOYMENT'
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
