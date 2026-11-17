import deckyPlugin from "@decky/rollup";
import typescript from "@rollup/plugin-typescript";

const config = deckyPlugin();
config.plugins = config.plugins.map((plugin) =>
  plugin.name === "typescript"
    ? typescript({
        tsconfig: false,
        compilerOptions: { jsx: "react-jsx", target: "ES2020", module: "ESNext" },
      })
    : plugin
);

export default config;
