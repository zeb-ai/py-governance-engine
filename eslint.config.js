module.exports = [
  {
    files: ["**/*.js"],
    rules: {
      "no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_" },
      ],
      "no-undef": "error",
    },
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "commonjs",
      globals: {
        require: "readonly",
        module: "readonly",
        exports: "readonly",
        __dirname: "readonly",
        __filename: "readonly",
        console: "readonly",
        process: "readonly",
        Buffer: "readonly",
      },
    },
  },
  {
    files: ["playground/**/*.js"],
    languageOptions: {
      sourceType: "module",
    },
  },
];
