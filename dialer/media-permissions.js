(function attach(globalScope) {
  function resolveMediaPermissionContext({
    mediaDevices,
    permissions,
    scope = globalScope,
  } = {}) {
    if (mediaDevices) {
      return { mediaDevices, permissions };
    }

    const fallbackNavigator = scope && scope.navigator ? scope.navigator : null;

    try {
      const topScope = scope && scope.top ? scope.top : null;
      if (
        topScope &&
        topScope !== scope &&
        topScope.location &&
        scope.location &&
        topScope.location.origin === scope.location.origin &&
        topScope.navigator
      ) {
        return {
          mediaDevices: topScope.navigator.mediaDevices,
          permissions: permissions || topScope.navigator.permissions,
        };
      }
    } catch {}

    return {
      mediaDevices: fallbackNavigator ? fallbackNavigator.mediaDevices : undefined,
      permissions: permissions || (fallbackNavigator ? fallbackNavigator.permissions : undefined),
    };
  }

  function createTimeoutPromise(timeoutMs) {
    return new Promise((_, reject) => {
      globalScope.setTimeout(() => {
        reject(new Error('Microphone permission timeout'));
      }, timeoutMs);
    });
  }

  async function ensureMicrophonePermission({
    mediaDevices,
    permissions,
    showToast,
    timeoutMs = 4000,
  }) {
    const context = resolveMediaPermissionContext({ mediaDevices, permissions });

    if (!context.mediaDevices || typeof context.mediaDevices.getUserMedia !== 'function') {
      showToast('Microphone access is required to place calls.');
      return false;
    }

    try {
      if (context.permissions && typeof context.permissions.query === 'function') {
        const permissionStatus = await context.permissions.query({ name: 'microphone' });
        if (permissionStatus && permissionStatus.state === 'denied') {
          showToast('Microphone is blocked. Allow it for localhost:3004 and try again.');
          return false;
        }
      }

      const stream = await Promise.race([
        context.mediaDevices.getUserMedia({ audio: true }),
        createTimeoutPromise(timeoutMs),
      ]);
      for (const track of stream.getTracks()) {
        track.stop();
      }
      return true;
    } catch (error) {
      console.error('[twilio] microphone permission failed:', error);
      if (error && error.message === 'Microphone permission timeout') {
        showToast('Microphone prompt timed out. Allow it for localhost:3004 and try again.');
        return false;
      }
      showToast('Microphone access is required to place calls.');
      return false;
    }
  }

  const api = { ensureMicrophonePermission, resolveMediaPermissionContext };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }

  globalScope.CallLockMediaPermissions = api;
})(typeof window !== 'undefined' ? window : globalThis);
