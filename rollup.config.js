import { defineConfig } from "rollup";
import typescript from "@rollup/plugin-typescript";
import commonjs from "@rollup/plugin-commonjs";
import resolve from "@rollup/plugin-node-resolve";

export default defineConfig({
  input: "src/index.tsx",
  output: {
    file: "dist/index.js",
    format: "cjs",
  },
  external: ["react", "@decky/ui", "@decky/api", "react-icons/fa"],
  plugins: [
    resolve({
      browser: true,
      preferBuiltins: false,
    }),
    typescript({
      tsconfig: false,
      compilerOptions: {
        jsx: "react-jsx",
        target: "ES2020",
        module: "ESNext",
      },
    }),
    commonjs(),
  ],
});
