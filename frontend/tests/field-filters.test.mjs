import test from 'node:test';
import assert from 'node:assert/strict';
import { filterFields, sortPortfolio } from '../lib/field-filters.ts';

const fields = [
  { field_id: 'f1', name: 'North', district: 'Dhaka', field_type: 'rice_awd', area_ha: null, created_at: null },
  { field_id: 'f2', name: 'South', district: 'Sylhet', field_type: 'cropland_alm_vm0042', area_ha: 12, created_at: '2026-01-01' },
  { field_id: 'f3', name: 'East', district: 'Dhaka', field_type: 'rice_awd', area_ha: 0, created_at: '2026-02-01' },
];
test('search combines with methodology and trims case-insensitive queries', () => {
  assert.deepEqual(filterFields(fields, ' DHAKA ', 'rice_awd', 'name').map(f => f.name), ['East', 'North']);
  assert.deepEqual(filterFields(fields, 'f2', 'rice_awd', 'name'), []);
  assert.equal(filterFields(fields, 'f2', 'all', 'name')[0].name, 'South');
});
test('area and date sorts put unknown values last without mutating input', () => {
  assert.deepEqual(filterFields(fields, '', 'all', 'area').map(f => f.name), ['South', 'East', 'North']);
  assert.deepEqual(filterFields(fields, '', 'all', 'newest').map(f => f.name), ['East', 'South', 'North']);
  assert.equal(fields[0].name, 'North');
});
test('portfolio numeric sort preserves zero and places missing values last in both directions', () => {
  const entries = fields.map(f => ({ ...f, final_issuance: f.area_ha, calculated_at: f.created_at }));
  assert.deepEqual(sortPortfolio(entries, 'final_issuance', 'asc').map(f => f.name), ['East', 'South', 'North']);
  assert.deepEqual(sortPortfolio(entries, 'final_issuance', 'desc').map(f => f.name), ['South', 'East', 'North']);
  assert.equal(entries[0].name, 'North');
});
test('empty datasets and missing numeric values sort safely', () => {
  assert.deepEqual(filterFields([], '', 'all', 'name'), []);
  assert.deepEqual(sortPortfolio([], 'name', 'asc'), []);
  assert.deepEqual(filterFields(fields.map(f => ({ ...f, area_ha: null })), '', 'all', 'area').map(f => f.name), ['East', 'North', 'South']);
});
