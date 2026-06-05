const path = require("path");
const bindings = require(
  path.join(__dirname, "..", "build", "Release", "grc_interceptor.node"),
);

module.exports = bindings;
