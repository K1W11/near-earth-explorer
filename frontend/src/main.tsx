import { css, type Component } from "dreamland/core";
import { Router, Route, router } from "dreamland/router";

import { MainView } from "./views/MainView";
import { AppView } from "./views/AppView";
import { NotFoundView } from "./views/NotFoundView";
import { Layout } from "./components/Layout";

const App: Component<{ url?: string }> = function () {
	const initialPath =
		this.url ?? (typeof location === "undefined" ? "/" : location.pathname);

	const routeTree = (
		<Router>
			<Route show={() => <MainView />} />
			<Route path="app" show={() => <AppView />} />
			<Route path="*" show={() => <NotFoundView />} />
		</Router>
	);
	router.route(initialPath, "http://localhost");
	return (
		<div id="app">
			<Layout>{routeTree}</Layout>
		</div>
	);
};

App.style = css`
	:global(:root) {
		font-family: Inter, ui-sans-serif, system-ui, sans-serif;
		color: white;
		color-scheme: dark;
		background: black;
		font-synthesis: none;
		text-rendering: optimizeLegibility;
		-webkit-font-smoothing: antialiased;
	}

	:global(*) {
		box-sizing: border-box;
	}

	:global(body) {
		margin: 0;
		min-width: 320px;
	}

	:global(a) {
		color: inherit;
		text-decoration: none;
	}

	:global(button) {
		font: inherit;
	}
`;

export default (url?: string) => <App url={url} />;