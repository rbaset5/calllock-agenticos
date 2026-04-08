function normalizeStatusCallback(body = {}) {
  return {
    callSid: body.CallSid || null,
    parentCallSid: body.ParentCallSid || null,
    callStatus: body.CallStatus || null,
    dialCallStatus: body.DialCallStatus || null,
    answeredBy: body.AnsweredBy || null,
    from: body.From || null,
    to: body.To || null,
    caller: body.Caller || null,
    called: body.Called || null,
    callDuration: body.CallDuration || null,
    timestamp: body.Timestamp || null,
    direction: body.Direction || null,
    sipResponseCode: body.SipResponseCode || null,
  };
}

function captureStatusCallback(storeCall, body = {}) {
  const normalized = normalizeStatusCallback(body);
  if (!normalized.callSid) return null;

  storeCall(normalized.callSid, {
    lastStatusCallback: normalized,
  });

  if (normalized.parentCallSid) {
    storeCall(normalized.parentCallSid, {
      lastChildStatusCallback: {
        ...normalized,
        childCallSid: normalized.callSid,
      },
    });
  }

  return normalized;
}

function registerStatusCallbackRoute(app, { validateTwilioSignature, storeCall, logger = console }) {
  app.post('/callbacks/status', validateTwilioSignature, (req, res) => {
    const normalized = captureStatusCallback(storeCall, req.body);

    if (normalized) {
      logger.log(
        `[status] CallSid=${normalized.callSid} parent=${normalized.parentCallSid || '-'} status=${normalized.callStatus || '-'} dial=${normalized.dialCallStatus || '-'} answeredBy=${normalized.answeredBy || '-'}`
      );
    } else {
      logger.log('[status] Ignored callback with missing CallSid');
    }

    res.sendStatus(200);
  });
}

module.exports = {
  normalizeStatusCallback,
  captureStatusCallback,
  registerStatusCallbackRoute,
};
