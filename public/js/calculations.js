// CA MUTCD 2026, Tables 6B-2 through 6B-4 and 6K-101(CA), and Section 4I.06.
(() => {
  const bufferFeet = [115, 155, 200, 250, 305, 360, 425, 495, 570, 645, 730, 820];
  const conflictFeet = [10, 12, 15, 17, 20, 22, 25, 25, 25, 25, 25, 25];

  function levelRoadSightDistance(speed) {
    const index = (speed - 20) / 5;
    return Number.isInteger(index) && index >= 0 && index < bufferFeet.length ? bufferFeet[index] : null;
  }

  function rampRun(rise, slope) {
    if (![rise,slope].every(Number.isFinite) || rise <= 0 || slope <= 0) return null;
    return (rise / 12) / (slope / 100);
  }

  function workZone(speed, width) {
    const row = (speed - 20) / 5;
    if (!Number.isInteger(row) || row < 0 || row >= bufferFeet.length || !Number.isFinite(width) || width <= 0) return null;
    const length = speed <= 40 ? width * speed * speed / 60 : width * speed;
    return {
      merge: Math.ceil(length), shift: Math.ceil(length / 2), shoulder: Math.ceil(length / 3),
      buffer: levelRoadSightDistance(speed), taper: Math.min(speed, 50), tangent: Math.min(2 * speed, 100),
      conflict: conflictFeet[row], specialSpacing: 20,
    };
  }

  function pedestrian(distance, requestedWalk, speed, buffer, offset) {
    if (![distance, requestedWalk, speed, buffer, offset].every(Number.isFinite) ||
        distance <= 0 || !Number.isInteger(requestedWalk) || requestedWalk < 4 ||
        speed <= 0 || speed > 3.5 || !Number.isInteger(buffer) || buffer < 2 || offset < 0) return null;
    const clearance = Math.max(buffer, Math.ceil(distance / speed));
    const totalMinimum = Math.ceil((offset + distance) / 3);
    const walk = Math.max(requestedWalk, totalMinimum - clearance);
    return { walk, change: clearance - buffer, buffer, clearance, totalMinimum, total: walk + clearance };
  }

  globalThis.SSSCalculations = { workZone, pedestrian, levelRoadSightDistance, rampRun };
})();
