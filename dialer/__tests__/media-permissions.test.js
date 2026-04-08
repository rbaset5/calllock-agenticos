const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

const {
  ensureMicrophonePermission,
  resolveMediaPermissionContext,
} = require('../media-permissions.js');

describe('resolveMediaPermissionContext', () => {
  it('prefers the top-level navigator for same-origin iframe callers', () => {
    const topMediaDevices = { getUserMedia() {} };
    const topPermissions = { query() {} };
    const currentMediaDevices = { getUserMedia() {} };
    const currentPermissions = { query() {} };

    const context = resolveMediaPermissionContext({
      scope: {
        location: { origin: 'http://localhost:3004' },
        navigator: {
          mediaDevices: currentMediaDevices,
          permissions: currentPermissions,
        },
        top: {
          location: { origin: 'http://localhost:3004' },
          navigator: {
            mediaDevices: topMediaDevices,
            permissions: topPermissions,
          },
        },
      },
    });

    assert.equal(context.mediaDevices, topMediaDevices);
    assert.equal(context.permissions, topPermissions);
  });

  it('falls back to the current frame navigator when top is unavailable', () => {
    const currentMediaDevices = { getUserMedia() {} };
    const currentPermissions = { query() {} };

    const context = resolveMediaPermissionContext({
      scope: {
        navigator: {
          mediaDevices: currentMediaDevices,
          permissions: currentPermissions,
        },
      },
    });

    assert.equal(context.mediaDevices, currentMediaDevices);
    assert.equal(context.permissions, currentPermissions);
  });
});

describe('ensureMicrophonePermission', () => {
  it('requests audio and stops tracks after success', async () => {
    let stopped = 0;
    const stream = {
      getTracks() {
        return [{ stop() { stopped += 1; } }, { stop() { stopped += 1; } }];
      },
    };

    let requested = false;
    const ok = await ensureMicrophonePermission({
      mediaDevices: {
        async getUserMedia(constraints) {
          requested = true;
          assert.deepEqual(constraints, { audio: true });
          return stream;
        },
      },
      showToast: () => {},
    });

    assert.equal(ok, true);
    assert.equal(requested, true);
    assert.equal(stopped, 2);
  });

  it('shows a toast and returns false when microphone access fails', async () => {
    const toasts = [];
    const ok = await ensureMicrophonePermission({
      mediaDevices: {
        async getUserMedia() {
          throw new Error('Permission denied');
        },
      },
      showToast(message) {
        toasts.push(message);
      },
    });

    assert.equal(ok, false);
    assert.deepEqual(toasts, ['Microphone access is required to place calls.']);
  });

  it('short-circuits when microphone permission is already denied', async () => {
    let requested = false;
    const toasts = [];
    const ok = await ensureMicrophonePermission({
      permissions: {
        async query(descriptor) {
          assert.deepEqual(descriptor, { name: 'microphone' });
          return { state: 'denied' };
        },
      },
      mediaDevices: {
        async getUserMedia() {
          requested = true;
          return null;
        },
      },
      showToast(message) {
        toasts.push(message);
      },
    });

    assert.equal(ok, false);
    assert.equal(requested, false);
    assert.deepEqual(toasts, ['Microphone is blocked. Allow it for localhost:3004 and try again.']);
  });

  it('times out when the browser never resolves the microphone request', async () => {
    const toasts = [];
    const ok = await ensureMicrophonePermission({
      mediaDevices: {
        async getUserMedia() {
          return new Promise(() => {});
        },
      },
      showToast(message) {
        toasts.push(message);
      },
      timeoutMs: 5,
    });

    assert.equal(ok, false);
    assert.deepEqual(toasts, ['Microphone prompt timed out. Allow it for localhost:3004 and try again.']);
  });
});
