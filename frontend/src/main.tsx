import { css, type Component } from "dreamland/core";
import { Router, Route } from "dreamland/router";
import { createDelegate } from "dreamland/core";

import { MainView } from "./views/MainView";
import { AppView } from "./views/AppView";
import { NotFoundView } from "./views/NotFoundView";
import { createLayout } from "./components/Layout";

const App: Component<{ url?: string }> = function () {
	const setStarSpeedEased = createDelegate<number>();

	return (
		<div id="app">
			<Router initial={this.url ? [this.url, "http://127.0.0.1:5173"] : []}>
				<Route layout={createLayout(setStarSpeedEased)}>
					<Route show={() => <MainView />} />
					<Route path="app" show={() => <AppView />} />
					<Route path="*" show={() => <NotFoundView />} />
				</Route>
			</Router>
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