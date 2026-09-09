'use strict';

const requestedAction = globalThis.MYQ_ACTION || 'probe';
const execute = globalThis.MYQ_EXECUTE === true;
const refreshDelayMs = 1400;
const maxRefreshAttempts = execute ? 7 : 4;

function emit(kind, data) {
  console.log(JSON.stringify({ kind: kind, data: data, ts: Date.now() }));
}

Java.perform(function () {
  try {
    const SDK = Java.use('myq.sdk.b');
    const DeviceApiImpl = Java.use('myq.sdk.external.api.device.DeviceApiImpl');
    const Device = Java.use('myq.sdk.data.model.q');
    const V = Java.use('myq.sdk.common.misc.v');
    const CommandApi = Java.use('myq.sdk.common.misc.communication.method.k');
    const Callback = Java.use('myq.sdk.data.model.communication.a$c');
    const api = Java.cast(SDK.E.value.getValue(), DeviceApiImpl);
    const accountManager = V.c();
    const accountId = accountManager.g();

    if (!accountId || accountId.length === 0) {
      emit('blocked', { reason: 'no_active_account' });
      return;
    }

    if (!execute) {
      const Wrapper = Java.use('com.chamberlain.network.framework.service.api.v6.devices.a$a');
      const closeWrap = Wrapper.a.overload(
        'com.chamberlain.network.framework.service.api.v6.devices.a',
        'com.chamberlain.network.a', 'java.lang.String', 'java.lang.String',
        'com.chamberlain.network.framework.m', 'int', 'java.lang.Object');
      const openWrap = Wrapper.f.overload(
        'com.chamberlain.network.framework.service.api.v6.devices.a',
        'com.chamberlain.network.a', 'java.lang.String', 'java.lang.String',
        'com.chamberlain.network.framework.m', 'int', 'java.lang.Object');
      closeWrap.implementation = function (service, version, account, serial, callback, mask, marker) {
        emit('suppressed', { action: 'close', account_present: !!account, serial_present: !!serial });
        return;
      };
      openWrap.implementation = function (service, version, account, serial, callback, mask, marker) {
        emit('suppressed', { action: 'open', account_present: !!account, serial_present: !!serial });
        return;
      };
    }

    const NoopCallback = Java.registerClass({
      name: 'com.tahlor.frida.GarageCallback' + Date.now(),
      implements: [Callback],
      methods: {
        a: [{
          returnType: 'void',
          argumentTypes: ['myq.sdk.data.model.communication.a$b'],
          implementation: function (result) { emit('command_callback', { received: true }); }
        }]
      }
    });

    function garageSnapshot() {
      const doors = api.T();
      if (!doors || doors.size() !== 1) {
        return { ok: false, reason: 'garage_count', count: doors ? doors.size() : -1 };
      }
      const raw = doors.get(0);
      const door = Java.cast(raw, Device);
      let state = 'UNKNOWN';
      try { state = door.T().toString(); } catch (e) {}
      return { ok: true, door: door, state: state, class_name: raw.getClass().getName().toString() };
    }

    function refreshThen(callback) {
      Java.scheduleOnMainThread(function () {
        try { api.M(accountId, null); }
        catch (e) { emit('refresh_error', { error: String(e) }); }
      });
      setTimeout(callback, refreshDelayMs);
    }

    function dispatch(snapshot) {
      const state = snapshot.state;
      emit('preflight', { garage_count: 1, state: state, class_name: snapshot.class_name, execute: execute });
      if (state !== 'OPEN' && state !== 'CLOSED') {
        emit('blocked', { reason: 'unstable_state', state: state });
        return;
      }

      if (requestedAction === 'open' && state === 'OPEN') {
        emit('noop', { action: 'open', state: state });
        return;
      }
      if (requestedAction === 'close' && state === 'CLOSED') {
        emit('noop', { action: 'close', state: state });
        return;
      }

      const command = Java.cast(V.u().C(), CommandApi);
      const callback = NoopCallback.$new();
      Java.scheduleOnMainThread(function () {
        try {
          if (requestedAction === 'probe') {
            command.j(snapshot.door, callback);
            emit('invoked', { action: 'open_internal' });
            command.c(snapshot.door, callback);
            emit('invoked', { action: 'close_internal' });
            emit('dispatch_complete', { network_calls_suppressed: true });
          } else if (requestedAction === 'open') {
            command.j(snapshot.door, callback);
            emit('invoked', { action: 'open_internal', execute: execute });
            if (execute) verifyTarget('OPEN', 1);
          } else if (requestedAction === 'close') {
            command.c(snapshot.door, callback);
            emit('invoked', { action: 'close_internal', execute: execute });
            if (execute) verifyTarget('CLOSED', 1);
          } else {
            emit('blocked', { reason: 'unsupported_action' });
          }
        } catch (e) {
          emit('dispatch_error', { error: String(e), stack: e.stack || '' });
        }
      });
    }

    function verifyTarget(target, attempt) {
      setTimeout(function () {
        refreshThen(function () {
          const snapshot = garageSnapshot();
          if (!snapshot.ok) {
            emit('verify_state', { attempt: attempt, state: 'UNKNOWN', reason: snapshot.reason });
          } else {
            emit('verify_state', { attempt: attempt, state: snapshot.state });
            if (snapshot.state === target) {
              emit('verified', { state: target, attempts: attempt });
              return;
            }
          }
          if (attempt < maxRefreshAttempts) verifyTarget(target, attempt + 1);
          else emit('unverified', { target: target, attempts: attempt, do_not_retry_command: true });
        });
      }, 350);
    }

    function initialize(attempt) {
      refreshThen(function () {
        const snapshot = garageSnapshot();
        if (snapshot.ok) {
          dispatch(snapshot);
          return;
        }
        if (attempt < maxRefreshAttempts) initialize(attempt + 1);
        else emit('blocked', { reason: snapshot.reason, count: snapshot.count, attempts: attempt });
      });
    }

    initialize(1);
  } catch (e) {
    emit('fatal', { error: String(e), stack: e.stack || '' });
  }
});