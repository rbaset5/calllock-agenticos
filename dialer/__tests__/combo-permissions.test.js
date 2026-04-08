const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

describe('combo iframe permissions', () => {
  it('grants microphone and autoplay permissions to both embedded apps', () => {
    const html = fs.readFileSync(path.join(__dirname, '..', 'combo.html'), 'utf8');
    const iframeTags = [...html.matchAll(/<iframe[^>]+id="([^"]+)"[^>]*allow="([^"]+)"/g)];
    const permissions = Object.fromEntries(iframeTags.map(([, id, allow]) => [id, allow]));

    assert.match(permissions['dialer-frame'], /microphone/);
    assert.match(permissions['dialer-frame'], /autoplay/);
    assert.match(permissions['hud-frame'], /microphone/);
    assert.match(permissions['hud-frame'], /autoplay/);
  });
});
