const test = require('node:test')
const assert = require('node:assert')
const Model = require('../Model.js')

const EVENTS = [
  { id: 'a', dateKey: '2026-08-10', title: 'Standup', color: '#f83a22', start: '2026-08-10T09:00:00-05:00' },
  { id: 'b', dateKey: '2026-08-10', title: 'Lunch', color: '#7bd148', start: '2026-08-10T12:00:00-05:00' },
  { id: 'c', dateKey: '2026-08-10', title: 'Retro', color: '#f83a22', start: '2026-08-10T16:00:00-05:00' },
  { id: 'd', dateKey: '2026-08-12', title: 'Dentist', color: '#ffad46', start: '2026-08-12T10:00:00-05:00' }
]

test('indexEventsByDate groups by dateKey', () => {
  const index = Model.indexEventsByDate(EVENTS)
  assert.equal(index['2026-08-10'].length, 3)
  assert.equal(index['2026-08-12'].length, 1)
  assert.equal(index['2026-08-11'], undefined)
})

test('indexEventsByDate tolerates an empty list', () => {
  assert.deepEqual(Model.indexEventsByDate([]), {})
})

test('indexEventsByDate tolerates null', () => {
  assert.deepEqual(Model.indexEventsByDate(null), {})
})

test('eventsForDateKey returns an empty array for an unknown day', () => {
  const index = Model.indexEventsByDate(EVENTS)
  assert.deepEqual(Model.eventsForDateKey(index, '2026-01-01'), [])
})

test('eventColors dedupes and preserves first-seen order', () => {
  const index = Model.indexEventsByDate(EVENTS)
  assert.deepEqual(Model.eventColors(index, '2026-08-10', 5), ['#f83a22', '#7bd148'])
})

test('eventColors respects the limit', () => {
  const index = Model.indexEventsByDate(EVENTS)
  assert.deepEqual(Model.eventColors(index, '2026-08-10', 1), ['#f83a22'])
})

// monthGrid returns an array of 6 week objects, each { week, days }.
// It is not wrapped in an outer object.
test('monthGrid without an index behaves as before', () => {
  const weeks = Model.monthGrid(2026, 7, 1, '2026-08-10')
  assert.equal(weeks.length, 6)
  const cells = weeks.flatMap(week => week.days)
  assert.equal(cells.length, 42)
  assert.ok(cells.every(cell => cell.hasEvent === false))
  assert.ok(cells.every(cell => Array.isArray(cell.dots) && cell.dots.length === 0))
})

test('monthGrid marks days that have events', () => {
  const index = Model.indexEventsByDate(EVENTS)
  const cells = Model.monthGrid(2026, 7, 1, '2026-08-10', index).flatMap(week => week.days)
  const tenth = cells.find(cell => cell.key === '2026-08-10')
  const eleventh = cells.find(cell => cell.key === '2026-08-11')
  assert.equal(tenth.hasEvent, true)
  assert.deepEqual(tenth.dots, ['#f83a22', '#7bd148'])
  assert.equal(eleventh.hasEvent, false)
})

test('monthGrid preserves the existing cell fields', () => {
  const cells = Model.monthGrid(2026, 7, 1, '2026-08-10').flatMap(week => week.days)
  const tenth = cells.find(cell => cell.key === '2026-08-10')
  assert.equal(tenth.day, 10)
  assert.equal(tenth.inMonth, true)
  assert.equal(tenth.today, true)
})

test('syncState reports missing when there is no document', () => {
  assert.equal(Model.syncState(null, Date.parse('2026-08-10T12:00:00Z'), 300), 'missing')
})

test('syncState reports missing when syncedAt is absent', () => {
  assert.equal(Model.syncState({}, Date.parse('2026-08-10T12:00:00Z'), 300), 'missing')
})

test('syncState reports ok for a recent sync', () => {
  const doc = { syncedAt: '2026-08-10T11:58:00Z' }
  assert.equal(Model.syncState(doc, Date.parse('2026-08-10T12:00:00Z'), 300), 'ok')
})

test('syncState tolerates one missed run', () => {
  // 300s interval, staleness threshold is 4x that, so 15 minutes is still ok.
  const doc = { syncedAt: '2026-08-10T11:48:00Z' }
  assert.equal(Model.syncState(doc, Date.parse('2026-08-10T12:00:00Z'), 300), 'ok')
})

test('syncState reports stale past the threshold', () => {
  const doc = { syncedAt: '2026-08-10T10:00:00Z' }
  assert.equal(Model.syncState(doc, Date.parse('2026-08-10T12:00:00Z'), 300), 'stale')
})

test('syncState reports missing for an unparseable syncedAt', () => {
  const doc = { syncedAt: 'not a date' }
  assert.equal(Model.syncState(doc, Date.parse('2026-08-10T12:00:00Z'), 300), 'missing')
})
