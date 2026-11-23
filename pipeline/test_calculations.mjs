import assert from 'node:assert/strict';
import '../public/js/calculations.js';
const {workZone, pedestrian} = globalThis.SSSCalculations;
assert.deepEqual(workZone(65,12), {merge:780,shift:390,shoulder:260,buffer:645,taper:50,tangent:100,conflict:25,specialSpacing:20});
assert.deepEqual(pedestrian(120,4,3.5,2,6), {walk:7,change:33,buffer:2,clearance:35,totalMinimum:42,total:42});
assert.equal(workZone(37,12),null);
assert.equal(pedestrian(120,7,3.5,1,6),null);

const {rampRun, levelRoadSightDistance} = globalThis.SSSCalculations;
assert.equal(rampRun(6, 7.5), 20/3);
assert.equal(rampRun(6, NaN), null);
assert.equal(rampRun(-1, 5), null);
assert.equal(levelRoadSightDistance(65), 645);
assert.equal(levelRoadSightDistance(34), null);
