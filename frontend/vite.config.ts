import type { UserConfig } from "vite";
import { devSsr } from "dreamland/vite";

export default {
	define: {
		__BUILD_DATE__: JSON.stringify(new Date().toISOString()),
	},
	plugins: [
		devSsr({
			entry: "/src/main-server.ts",
		}),
	],
} satisfies UserConfig;