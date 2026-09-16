import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";

export function NotFoundRoute() { return <main className="center-page not-found"><span className="eyebrow">404</span><h1>This page is outside the ledger.</h1><p>The address may be outdated or incomplete.</p><Button onClick={() => history.back()} variant="secondary">Go back</Button><Link to="/">Return home</Link></main>; }
