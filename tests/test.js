const { start, stop } = require('../index');

function test(description, fn) {
  try {
    fn();
    console.log(`✓ ${description}`);
  } catch (e) {
    console.error(`✗ ${description}: ${e.message}`);
    process.exit(1);
  }
}

test('start/stop', () => {
  start();
  stop();
});

console.log('All tests passed.');