export type Role = 'admin' | 'verifier' | 'member'
export interface User { id: string; email: string; display_name: string; role: Role; is_active: boolean; created_at?: string }
export interface Project { id: string; owner_id: string; name: string; project_type: string; region: string; methodology: string; description: string; estimated_tonnes: string; status: 'draft'|'pending'|'approved'|'rejected'; review_note?: string; created_at: string }
export interface ProjectDocument { id:string; project_id:string; category:string; original_name:string; content_type:string; size_bytes:number; created_at:string }
export interface ApplicationReadiness { ready:boolean; completed_categories:string[]; missing_categories:string[]; completion_percent:number }
export type AgentDraft = Partial<Record<'name'|'project_type'|'region'|'methodology'|'description'|'estimated_tonnes',string>>
export interface AgentReply { draft?:AgentDraft; missing_fields:string[]; model_available:boolean; reply:string; stage:string; suggested_actions:string[]; readiness?:ApplicationReadiness }
export interface Batch { id: string; project_id: string; vintage: number; methodology: string; serial_prefix: string; total_issued: string; total_retired: string; issued_at: string }
export interface Holding { batch_id: string; quantity: string; locked_quantity: string }
export interface Listing { id: string; seller_id: string; batch_id: string; quantity: string; remaining_quantity: string; unit_price: string; currency: string; status: string; created_at: string }
export interface Trade { id: string; listing_id: string; buyer_id: string; seller_id: string; batch_id: string; quantity: string; unit_price: string; total_amount: string; currency: string; traded_at: string }
export interface Retirement { id: string; certificate_no: string; user_id: string; batch_id: string; quantity: string; beneficiary: string; reason: string; retired_at: string }
export interface Ledger { id:string; batch_id:string; kind:string; quantity_delta:string; balance_after:string; reference_type:string; reference_id:string; created_at:string }
export interface Dashboard { total_issued: string; total_retired: string; open_market_quantity: string; trade_volume: string; project_count: number }
export interface BlockchainConfig { enabled:boolean; configured:boolean; network:string; chain_id:number; rpc_url?:string; confirmations:number; project_contract_address?:string; credit_contract_address?:string; operator_address?:string; signing_mode:string }
export interface ChainOperation { id:string; operation_type:string; resource_type:string; resource_id:string; chain_id:number; contract_address:string; payload:Record<string,unknown>; status:string; attempts:number; transaction_hash?:string; block_number?:number; error_message?:string; created_at:string }
export interface AuditEvent { id:string; actor_id?:string; action:string; resource_type:string; resource_id:string; detail:string; created_at:string }
