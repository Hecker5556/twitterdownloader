#!/usr/bin/env node
const vm = require('vm');

let inputBuffer = '';

process.stdin.on('data', (chunk) => {
  inputBuffer += chunk;
});

process.stdin.on('end', () => {
  try {
    let scripts = [];

    const hasScriptTags = /<script[\s>]/i.test(inputBuffer);

    if (hasScriptTags) {
      const scriptRegex = /<script[^>]*>([\s\S]*?)<\/script>/gi;
      let match;
      while ((match = scriptRegex.exec(inputBuffer)) !== null) {
        let code = match[1].trim();
        if (
          code.includes('$R') ||
          code.includes('$_TSR') ||
          code.includes('tsr-stream') ||
          code.includes('GraphQLRequestStream')
        ) {
          code = code
            .replace(/\{let s=document\.currentScript[\s\S]*$/, '')
            .replace(/document\.currentScript\.remove\(\);?/g, '')
            .replace(/\/\*$tsr-stream-boundary\*\/\s*/g, '')
            .trim();
          if (code) scripts.push(code);
        }
      }
    } else {
      const parts = inputBuffer
        .split(/(?=\(self\.\$R=self\.\$R\|\|\{})|(?=\(\$R=>\$R\[\d+\]\.next)/)
        .map(s => s.trim())
        .filter(Boolean);

      scripts = parts.length > 0 ? parts : [inputBuffer.trim()];
    }

    if (scripts.length === 0 || !scripts[0]) {
      console.error('No relevant scripts found');
      process.exit(1);
    }

    const context = {
      self: {},
      document: {
        currentScript: { remove() {} },
        dispatchEvent() {},
      },
      ReadableStream: class {
        constructor() {}
      },
      performance: { now: () => Date.now() },
      requestAnimationFrame: (cb) => typeof cb === 'function' && cb(),
      $_TSR: {},
    };

    context.self.$R = { tsr: [] };
    context.$R = context.self.$R;
    vm.createContext(context);

    for (const code of scripts) {
      try {
        vm.runInContext(code, context);
      } catch (e) {
        // console.error('Script error (non-fatal):', e.message);
      }
    }

    if (typeof context.$_TSR?.router === 'function') {
      try {
        context.$_TSR.router(context.self.$R.tsr);
      } catch (e) {}
    }

    if (context.self.$R.tsr && context.self.$R.tsr[0]) {
      process.stdout.write(JSON.stringify(context.self.$R.tsr[0], null, 2) + '\n');
    } else {
      console.error('tsr[0] missing – dumping whole tsr');
      process.stdout.write(JSON.stringify(context.self.$R.tsr, null, 2) + '\n');
      process.exit(1);
    }
  } catch (err) {
    console.error('VM Execution Error:', err.message);
    process.exit(1);
  }
});