#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const SHOWDOWN_DIST = path.resolve(__dirname, "../../pokemon-showdown/dist/data");
const OUTPUT = path.resolve(__dirname, "../data/showdown_db.json");

const NON_STANDARD_SKIP = new Set(["Past", "Future", "LGPE", "CAP", "Custom", "Unobtainable"]);

function load(file) {
  return require(path.join(SHOWDOWN_DIST, file));
}

function stripFunctions(obj) {
  if (obj === null || obj === undefined) return obj;
  if (typeof obj !== "object") return obj;
  if (Array.isArray(obj)) return obj.map(stripFunctions);
  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    if (typeof v !== "function") out[k] = stripFunctions(v);
  }
  return out;
}

function extractPokedex() {
  const { Pokedex } = load("pokedex.js");
  const result = {};
  for (const [id, entry] of Object.entries(Pokedex)) {
    if (entry.isNonstandard && NON_STANDARD_SKIP.has(entry.isNonstandard)) continue;
    result[id] = {
      name: entry.name,
      num: entry.num,
      types: entry.types,
      baseStats: entry.baseStats,
      abilities: entry.abilities,
      weightkg: entry.weightkg,
      heightm: entry.heightm,
    };
    if (entry.baseSpecies) result[id].baseSpecies = entry.baseSpecies;
    if (entry.forme) result[id].forme = entry.forme;
    if (entry.otherFormes) result[id].otherFormes = entry.otherFormes;
    if (entry.evos) result[id].evos = entry.evos;
    if (entry.prevo) result[id].prevo = entry.prevo;
    if (entry.gender) result[id].gender = entry.gender;
    if (entry.genderRatio) result[id].genderRatio = entry.genderRatio;
  }
  return result;
}

function extractMoves() {
  const { Moves } = load("moves.js");
  const result = {};
  for (const [id, entry] of Object.entries(Moves)) {
    if (entry.isNonstandard && NON_STANDARD_SKIP.has(entry.isNonstandard)) continue;
    result[id] = {
      name: entry.name,
      num: entry.num,
      type: entry.type,
      basePower: entry.basePower,
      accuracy: entry.accuracy,
      category: entry.category,
      pp: entry.pp,
      priority: entry.priority,
      target: entry.target,
    };
    if (entry.flags) result[id].flags = stripFunctions(entry.flags);
  }
  return result;
}

function extractItems() {
  const { Items } = load("items.js");
  const result = {};
  for (const [id, entry] of Object.entries(Items)) {
    if (entry.isNonstandard && NON_STANDARD_SKIP.has(entry.isNonstandard)) continue;
    result[id] = {
      name: entry.name,
      num: entry.num,
    };
    if (entry.gen !== undefined) result[id].gen = entry.gen;
    if (entry.fling) result[id].fling = stripFunctions(entry.fling);
    if (entry.megaStone) result[id].megaStone = entry.megaStone;
    if (entry.zMove) result[id].zMove = entry.zMove;
  }
  return result;
}

function extractAbilities() {
  const { Abilities } = load("abilities.js");
  const result = {};
  for (const [id, entry] of Object.entries(Abilities)) {
    if (entry.isNonstandard && NON_STANDARD_SKIP.has(entry.isNonstandard)) continue;
    result[id] = {
      name: entry.name,
      num: entry.num,
      rating: entry.rating,
    };
  }
  return result;
}

function extractLearnsets() {
  const { Learnsets } = load("learnsets.js");
  const result = {};
  for (const [id, entry] of Object.entries(Learnsets)) {
    if (!entry.learnset) continue;
    const gen9Moves = {};
    for (const [moveId, sources] of Object.entries(entry.learnset)) {
      const gen9Sources = sources.filter((s) => s.startsWith("9"));
      if (gen9Sources.length > 0) gen9Moves[moveId] = gen9Sources;
    }
    if (Object.keys(gen9Moves).length > 0) {
      result[id] = { learnset: gen9Moves };
    }
  }
  return result;
}

function extractNatures() {
  const { Natures } = load("natures.js");
  const result = {};
  for (const [id, entry] of Object.entries(Natures)) {
    result[id] = { name: entry.name };
    if (entry.plus) result[id].plus = entry.plus;
    if (entry.minus) result[id].minus = entry.minus;
  }
  return result;
}

const db = {
  metadata: {
    generated_at: new Date().toISOString(),
    source: "pokemon-showdown/dist/data",
    description: "Extracted Showdown Gen 9 data for pokemon-battle-assistant",
  },
  pokedex: extractPokedex(),
  moves: extractMoves(),
  items: extractItems(),
  abilities: extractAbilities(),
  learnsets: extractLearnsets(),
  natures: extractNatures(),
};

const counts = {
  pokedex: Object.keys(db.pokedex).length,
  moves: Object.keys(db.moves).length,
  items: Object.keys(db.items).length,
  abilities: Object.keys(db.abilities).length,
  learnsets: Object.keys(db.learnsets).length,
  natures: Object.keys(db.natures).length,
};

fs.writeFileSync(OUTPUT, JSON.stringify(db, null, 0), "utf-8");

console.log("Showdown data extracted to:", OUTPUT);
console.log("Counts:", JSON.stringify(counts, null, 2));
console.log("File size:", (fs.statSync(OUTPUT).size / 1024 / 1024).toFixed(2), "MB");
