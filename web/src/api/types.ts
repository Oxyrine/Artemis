// Types come from the API's OpenAPI contract (contracts/openapi.json -> npm run gen:api); never hand-written.
import type { components } from './schema'

type S = components['schemas']
export type CaseList = S['CaseList']
export type CaseSummary = S['CaseSummary']
export type CaseDetail = S['CaseDetail']
export type EvidenceGraph = S['EvidenceGraph']
export type GraphNode = S['GraphNode']
export type TraceView = S['TraceView']
export type BatchStatus = S['BatchStatus']
export type Modes = S['Modes']
export type ModeInfo = S['ModeInfo']
export type MetricsReport = S['MetricsReport']
export type ReviewerView = S['ReviewerView']
export type ReviewResult = S['ReviewResult']
export type AuditList = S['AuditList']
export type AuditEvent = S['AuditEventView']
export type VerifyResult = S['VerifyResult']
export type FlagView = S['FlagView']
export type ReviewerActions = S['ReviewerActions']
export type RunMode = S['BatchRunRequest']['mode']
export type Decision = S['ReviewRequest']['decision']
export type Status = NonNullable<CaseSummary['status']>
export type VarianceClosure = NonNullable<CaseDetail['closure']>
export type EvidenceItem = CaseDetail['evidence'][number]
export type ProposedEntry = CaseDetail['proposed_entries'][number]
export type GraphEdge = EvidenceGraph['edges'][number]
