/* COP figures from Home Assistant's long-term statistics.
 *
 * A COP over a period is the heat delivered divided by the electricity used
 * over that period. It is never the mean of separate COP values.
 */

const HOUR_MS = 3600 * 1000;
const DAY_MS = 24 * HOUR_MS;

export const CHART_DAYS = 14;
const TWO_MONTHS_DAYS = 61;
const TWELVE_MONTHS_DAYS = 365;

function bucketStart(bucket) {
  return typeof bucket.start === 'number' ? bucket.start : Date.parse(bucket.start);
}

function bucketChange(bucket) {
  return typeof bucket.change === 'number' && Number.isFinite(bucket.change) ? bucket.change : null;
}

// The sum of all changes since `since`, or null when no bucket falls in range.
export function sumChange(buckets, since) {
  let total = null;
  for (const bucket of buckets || []) {
    const change = bucketChange(bucket);
    if (change === null || bucketStart(bucket) < since) continue;
    total = (total || 0) + change;
  }
  return total;
}

// The change of the bucket that starts closest to `time`. The tolerance covers
// daylight saving shifts and a browser in another time zone than the server.
export function changeNear(buckets, time, tolerance = DAY_MS / 2) {
  let best = null;
  let bestDistance = tolerance;
  for (const bucket of buckets || []) {
    const distance = Math.abs(bucketStart(bucket) - time);
    if (distance < bestDistance && bucketChange(bucket) !== null) {
      best = bucketChange(bucket);
      bestDistance = distance;
    }
  }
  return best;
}

// A day without electricity use has no COP at all, rather than 0.
export function ratio(heat, electricity) {
  if (heat === null || electricity === null || !(electricity > 0)) return null;
  return heat / electricity;
}

export function localMidnight(now) {
  const date = new Date(now);
  date.setHours(0, 0, 0, 0);
  return date.getTime();
}

function dayStart(midnight, daysAgo) {
  const date = new Date(midnight);
  date.setDate(date.getDate() - daysAgo);
  return date.getTime();
}

export function summarize(daily, hourly, heatId, elecId, now) {
  const heatDays = (daily && daily[heatId]) || [];
  const elecDays = (elecId && daily && daily[elecId]) || [];
  const heatHours = (hourly && hourly[heatId]) || [];
  const elecHours = (elecId && hourly && hourly[elecId]) || [];
  const midnight = localMidnight(now);

  const days = [];
  for (let i = 0; i < CHART_DAYS; i++) {
    const start = dayStart(midnight, CHART_DAYS - 1 - i);
    const heat = changeNear(heatDays, start);
    const electricity = changeNear(elecDays, start);
    days.push({ start, heat, electricity, cop: ratio(heat, electricity) });
  }

  const rolling = (heat, electricity, since) =>
    ratio(sumChange(heat, since), sumChange(electricity, since));

  return {
    days,
    heatToday: days[CHART_DAYS - 1].heat,
    elecToday: days[CHART_DAYS - 1].electricity,
    cop24: rolling(heatHours, elecHours, now - DAY_MS),
    cop2m: rolling(heatDays, elecDays, now - TWO_MONTHS_DAYS * DAY_MS),
    cop12m: rolling(heatDays, elecDays, now - TWELVE_MONTHS_DAYS * DAY_MS),
  };
}

// Uses the recorder's own websocket command, which is part of Home Assistant
// and not of this integration.
export async function fetchEnergy(hass, heatId, elecId, now = Date.now()) {
  const ids = [heatId, elecId].filter(Boolean);
  const request = (period, start) =>
    hass.callWS({
      type: 'recorder/statistics_during_period',
      start_time: new Date(start).toISOString(),
      end_time: new Date(now).toISOString(),
      statistic_ids: ids,
      period,
      types: ['change'],
      units: { energy: 'kWh' },
    });
  const [daily, hourly] = await Promise.all([
    request('day', now - (TWELVE_MONTHS_DAYS + 1) * DAY_MS),
    request('hour', now - DAY_MS - HOUR_MS),
  ]);
  return summarize(daily, hourly, heatId, elecId, now);
}
