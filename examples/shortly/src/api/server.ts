import express from "express";
import { create, resolve } from "./links";
import { statsFor } from "./stats";

const app = express();
app.use(express.json());
app.post("/links", async (req, res) => res.status(201).json({ code: await create(req.body.url, req.body.owner) }));
app.get("/links/:code/stats", async (req, res) => res.json(await statsFor(req.params.code)));
app.get("/:code", async (req, res) => res.redirect(301, await resolve(req.params.code)));
app.listen(8080);
