const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

const {
  captureStatusCallback,
  registerStatusCallbackRoute,
} = require('../status-callbacks.js');

describe('registerStatusCallbackRoute', () => {
  it('registers POST /callbacks/status', () => {
    const routes = [];
    const app = {
      post(path, ...handlers) {
        routes.push({ path, handlers });
      },
    };

    registerStatusCallbackRoute(app, {
      validateTwilioSignature: () => {},
      storeCall: () => {},
      logger: { log() {} },
    });

    assert.equal(routes.length, 1);
    assert.equal(routes[0].path, '/callbacks/status');
    assert.equal(routes[0].handlers.length, 2);
  });

  it('stores status details and responds 200 when the handler runs', () => {
    const routes = [];
    const callStore = new Map();
    const storeCall = (callSid, patch) => {
      const current = callStore.get(callSid) || {};
      callStore.set(callSid, { ...current, ...patch });
    };
    const app = {
      post(path, ...handlers) {
        routes.push({ path, handlers });
      },
    };

    registerStatusCallbackRoute(app, {
      validateTwilioSignature: (_req, _res, next) => next(),
      storeCall,
      logger: { log() {} },
    });

    const handler = routes[0].handlers[1];
    let statusCode = null;
    handler(
      {
        body: {
          CallSid: 'CA-child',
          ParentCallSid: 'CA-parent',
          CallStatus: 'completed',
          DialCallStatus: 'busy',
        },
      },
      {
        sendStatus(code) {
          statusCode = code;
        },
      }
    );

    assert.equal(statusCode, 200);
    assert.equal(callStore.get('CA-child').lastStatusCallback.dialCallStatus, 'busy');
    assert.equal(callStore.get('CA-parent').lastChildStatusCallback.childCallSid, 'CA-child');
  });
});

describe('captureStatusCallback', () => {
  it('stores normalized child and parent-leg status details', () => {
    const callStore = new Map();
    const storeCall = (callSid, patch) => {
      const current = callStore.get(callSid) || {};
      callStore.set(callSid, { ...current, ...patch });
    };

    const normalized = captureStatusCallback(storeCall, {
      CallSid: 'CA-child',
      ParentCallSid: 'CA-parent',
      CallStatus: 'completed',
      DialCallStatus: 'no-answer',
      AnsweredBy: 'unknown',
      From: '+13252164094',
      To: '+12487391087',
      Caller: 'client:calllock-agent',
      Called: '+12487391087',
      CallDuration: '0',
      Timestamp: 'Wed, 08 Apr 2026 12:35:53 +0000',
    });

    assert.deepEqual(normalized, {
      callSid: 'CA-child',
      parentCallSid: 'CA-parent',
      callStatus: 'completed',
      dialCallStatus: 'no-answer',
      answeredBy: 'unknown',
      from: '+13252164094',
      to: '+12487391087',
      caller: 'client:calllock-agent',
      called: '+12487391087',
      callDuration: '0',
      timestamp: 'Wed, 08 Apr 2026 12:35:53 +0000',
      direction: null,
      sipResponseCode: null,
    });

    assert.deepEqual(callStore.get('CA-child').lastStatusCallback, normalized);
    assert.deepEqual(callStore.get('CA-parent').lastChildStatusCallback, {
      ...normalized,
      childCallSid: 'CA-child',
    });
  });
});
