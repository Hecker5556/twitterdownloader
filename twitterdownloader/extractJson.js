#!/usr/bin/env node
const vm = require('vm');

let inputBuffer = '';

process.stdin.on('data', (chunk) => {
  inputBuffer += chunk;
});

process.stdin.on('end', () => {
  try {
    const context = {
      self: {},
      document: { currentScript: { remove() {} } },
      ReadableStream: class {},
      $_TSR: {}
    };

    context.self.$R = { tsr: [] };
    context.$R = context.self.$R;
    vm.createContext(context);
    vm.runInContext(inputBuffer, context);
    if (typeof context.$_TSR.router === 'function') {
      context.$_TSR.router(context.self.$R.tsr);
    }
    if (context.self.$R.tsr && context.self.$R.tsr[0]) {
      process.stdout.write(JSON.stringify(context.self.$R.tsr[0]) + '\n');
    } else {
      console.error('-1');
      process.exit(1);
    }
  } catch (err) {
    console.error('VM Execution Error:', err.message);
    process.exit(1);
  }
});