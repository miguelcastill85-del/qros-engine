export function bindProviderOrigin(origin, clientSource) {
  const pinned = clientSource.match(/static const trustedOrigin\s*=\s*'([^']+)'/);
  if (!pinned || pinned[1] !== origin || !/^https:\/\/qros-mobile-g12-test-only\.[a-z0-9-]+\.workers\.dev$/.test(origin)) {
    throw Error('PROVIDER_ORIGIN_DIFFERS_FROM_PINNED_ANDROID_PRODUCT');
  }
  return origin;
}
