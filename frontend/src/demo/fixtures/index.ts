/**
 * Pre-solved synthetic demo fixtures for Standalone Demo Mode (GitHub Pages)
 * Governed by SPECIFICATION.md Section 10 and DECISIONS.md ADR-007 / ADR-011.
 */

import { FactoryConfigResponse, ScheduleDetailResponse, VerificationReportResponse } from '../../types/api';
import demo1Json from './demo1_normal.json';
import demo2Json from './demo2_bottleneck.json';
import demo3Json from './demo3_highload.json';
import demo4Json from './demo4_urgent.json';
import demo5Json from './demo5_downtime.json';
import demo6Json from './demo6_invalid.json';

export interface DemoFixture {
  id: string;
  name: string;
  description: string;
  category: string;
  factory: FactoryConfigResponse;
  schedule: ScheduleDetailResponse;
  verification_report: VerificationReportResponse;
}

export const DEMO_FIXTURES: Record<string, DemoFixture> = {
  'demo-1': demo1Json as unknown as DemoFixture,
  'demo-2': demo2Json as unknown as DemoFixture,
  'demo-3': demo3Json as unknown as DemoFixture,
  'demo-4': demo4Json as unknown as DemoFixture,
  'demo-5': demo5Json as unknown as DemoFixture,
  'demo-6': demo6Json as unknown as DemoFixture,
};

export const DEMO_SCENARIO_LIST: DemoFixture[] = [
  DEMO_FIXTURES['demo-1'],
  DEMO_FIXTURES['demo-2'],
  DEMO_FIXTURES['demo-3'],
  DEMO_FIXTURES['demo-4'],
  DEMO_FIXTURES['demo-5'],
  DEMO_FIXTURES['demo-6'],
];

export function getDemoFixture(id: string): DemoFixture | undefined {
  return DEMO_FIXTURES[id];
}
