#!/bin/bash
set -e

cd "$(dirname "$0")"

rm -rf csrc build data
node scripts/vendor.js
npx node-gyp rebuild

echo "Done!"
