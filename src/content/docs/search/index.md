---
title: Search standards
description: Find section numbers, drawings, signs, and wording in the standards.
tableOfContents: false
pagefind: false
---

<form id="standards-search" class="standards-search" role="search">
<label for="standards-query">Code, topic, or exact wording</label>
<input list="query-guesses" id="standards-query" name="q" type="search" placeholder="E 664.12, MPP 531 S-418.6 sheet 8, or curb ramp" autocomplete="off" />
<label for="standards-source">Source</label>
<select id="standards-source" name="source">
<option value="">All sources</option><option>CA MUTCD</option><option>Federal MUTCD</option><option>Caltrans</option><option>LADOT</option><option>LA BOE</option><option>Local cities</option><option>Regional standards</option><option>Transit operators</option><option>Signs</option><option>Markings</option><option>Topics and tools</option><option>Guides and references</option>
</select>
<label for="issuer-filter">Issuer</label><select id="issuer-filter" name="issuer"><option value="">All issuers</option></select>
<label for="match-style">Match</label><select id="match-style" name="match"><option value="all">Titles and full text</option><option value="titles">Codes and titles</option><option value="exact">Exact identifier</option></select><datalist id="query-guesses"></datalist>
<button type="submit">Search</button>
</form>
<p id="standards-status" role="status" aria-live="polite"></p>
<ol id="standards-results" aria-label="Search results"></ol>
<button id="standards-more" type="button" hidden>Show more results</button>
<noscript>Search needs JavaScript. Browse the <a href="/SoCal-Super-Standards/keywords/">keyword index</a> or the <a href="/SoCal-Super-Standards/sources/">source directory</a>.</noscript>
