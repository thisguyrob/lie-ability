module.exports = {
  root: true,
  extends: ['eslint:recommended', 'plugin:react/recommended'],
  parserOptions: { ecmaVersion: 2022, sourceType: 'module' },
  settings: { react: { version: 'detect' } },
  env: { browser: true, es2022: true, node: true },
};
