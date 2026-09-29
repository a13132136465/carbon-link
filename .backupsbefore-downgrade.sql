--
-- PostgreSQL database dump
--

\restrict 3YIhccVverWjg4Qe0bHjlcypDW3ZD917Woj1pjBZLhMbTVnPWriVIUNt1WwvcfQ

-- Dumped from database version 17.11
-- Dumped by pg_dump version 17.11

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER TABLE IF EXISTS ONLY public.trades DROP CONSTRAINT IF EXISTS trades_seller_id_fkey;
ALTER TABLE IF EXISTS ONLY public.trades DROP CONSTRAINT IF EXISTS trades_listing_id_fkey;
ALTER TABLE IF EXISTS ONLY public.trades DROP CONSTRAINT IF EXISTS trades_buyer_id_fkey;
ALTER TABLE IF EXISTS ONLY public.trades DROP CONSTRAINT IF EXISTS trades_batch_id_fkey;
ALTER TABLE IF EXISTS ONLY public.retirements DROP CONSTRAINT IF EXISTS retirements_user_id_fkey;
ALTER TABLE IF EXISTS ONLY public.retirements DROP CONSTRAINT IF EXISTS retirements_batch_id_fkey;
ALTER TABLE IF EXISTS ONLY public.projects DROP CONSTRAINT IF EXISTS projects_reviewed_by_fkey;
ALTER TABLE IF EXISTS ONLY public.projects DROP CONSTRAINT IF EXISTS projects_owner_id_fkey;
ALTER TABLE IF EXISTS ONLY public.project_documents DROP CONSTRAINT IF EXISTS project_documents_uploaded_by_fkey;
ALTER TABLE IF EXISTS ONLY public.project_documents DROP CONSTRAINT IF EXISTS project_documents_project_id_fkey;
ALTER TABLE IF EXISTS ONLY public.password_reset_tokens DROP CONSTRAINT IF EXISTS password_reset_tokens_user_id_fkey;
ALTER TABLE IF EXISTS ONLY public.operation_requests DROP CONSTRAINT IF EXISTS operation_requests_user_id_fkey;
ALTER TABLE IF EXISTS ONLY public.listings DROP CONSTRAINT IF EXISTS listings_seller_id_fkey;
ALTER TABLE IF EXISTS ONLY public.listings DROP CONSTRAINT IF EXISTS listings_batch_id_fkey;
ALTER TABLE IF EXISTS ONLY public.ledger_entries DROP CONSTRAINT IF EXISTS ledger_entries_user_id_fkey;
ALTER TABLE IF EXISTS ONLY public.ledger_entries DROP CONSTRAINT IF EXISTS ledger_entries_batch_id_fkey;
ALTER TABLE IF EXISTS ONLY public.holdings DROP CONSTRAINT IF EXISTS holdings_user_id_fkey;
ALTER TABLE IF EXISTS ONLY public.holdings DROP CONSTRAINT IF EXISTS holdings_batch_id_fkey;
ALTER TABLE IF EXISTS ONLY public.credit_batches DROP CONSTRAINT IF EXISTS credit_batches_project_id_fkey;
ALTER TABLE IF EXISTS ONLY public.credit_batches DROP CONSTRAINT IF EXISTS credit_batches_issued_by_fkey;
ALTER TABLE IF EXISTS ONLY public.audit_events DROP CONSTRAINT IF EXISTS audit_events_actor_id_fkey;
DROP INDEX IF EXISTS public.ix_users_wallet_address;
DROP INDEX IF EXISTS public.ix_users_role;
DROP INDEX IF EXISTS public.ix_users_email;
DROP INDEX IF EXISTS public.ix_trades_seller_id;
DROP INDEX IF EXISTS public.ix_trades_listing_id;
DROP INDEX IF EXISTS public.ix_trades_buyer_id;
DROP INDEX IF EXISTS public.ix_retirements_user_id;
DROP INDEX IF EXISTS public.ix_retirements_certificate_no;
DROP INDEX IF EXISTS public.ix_retirements_batch_id;
DROP INDEX IF EXISTS public.ix_projects_status;
DROP INDEX IF EXISTS public.ix_projects_owner_id;
DROP INDEX IF EXISTS public.ix_project_documents_uploaded_by;
DROP INDEX IF EXISTS public.ix_project_documents_project_id;
DROP INDEX IF EXISTS public.ix_project_document_project_category;
DROP INDEX IF EXISTS public.ix_password_reset_tokens_user_id;
DROP INDEX IF EXISTS public.ix_password_reset_tokens_token_hash;
DROP INDEX IF EXISTS public.ix_password_reset_tokens_expires_at;
DROP INDEX IF EXISTS public.ix_operation_requests_user_id;
DROP INDEX IF EXISTS public.ix_listings_status;
DROP INDEX IF EXISTS public.ix_listings_seller_id;
DROP INDEX IF EXISTS public.ix_listings_batch_id;
DROP INDEX IF EXISTS public.ix_ledger_user_created;
DROP INDEX IF EXISTS public.ix_ledger_entries_user_id;
DROP INDEX IF EXISTS public.ix_ledger_entries_reference_id;
DROP INDEX IF EXISTS public.ix_ledger_entries_created_at;
DROP INDEX IF EXISTS public.ix_ledger_entries_batch_id;
DROP INDEX IF EXISTS public.ix_holdings_user_id;
DROP INDEX IF EXISTS public.ix_holdings_batch_id;
DROP INDEX IF EXISTS public.ix_credit_batches_project_id;
DROP INDEX IF EXISTS public.ix_chain_operations_status;
DROP INDEX IF EXISTS public.ix_chain_operations_resource_id;
DROP INDEX IF EXISTS public.ix_chain_operations_next_attempt_at;
DROP INDEX IF EXISTS public.ix_chain_operation_status_created;
DROP INDEX IF EXISTS public.ix_audit_events_resource_id;
DROP INDEX IF EXISTS public.ix_audit_events_actor_id;
DROP INDEX IF EXISTS public.ix_audit_events_action;
ALTER TABLE IF EXISTS ONLY public.users DROP CONSTRAINT IF EXISTS users_pkey;
ALTER TABLE IF EXISTS ONLY public.holdings DROP CONSTRAINT IF EXISTS uq_user_batch;
ALTER TABLE IF EXISTS ONLY public.retirements DROP CONSTRAINT IF EXISTS uq_retirements_transaction_hash;
ALTER TABLE IF EXISTS ONLY public.retirements DROP CONSTRAINT IF EXISTS uq_retirements_chain_id;
ALTER TABLE IF EXISTS ONLY public.projects DROP CONSTRAINT IF EXISTS uq_projects_chain_token_id;
ALTER TABLE IF EXISTS ONLY public.credit_batches DROP CONSTRAINT IF EXISTS uq_project_vintage;
ALTER TABLE IF EXISTS ONLY public.operation_requests DROP CONSTRAINT IF EXISTS uq_operation_request;
ALTER TABLE IF EXISTS ONLY public.credit_batches DROP CONSTRAINT IF EXISTS uq_credit_batches_chain_batch_id;
ALTER TABLE IF EXISTS ONLY public.chain_operations DROP CONSTRAINT IF EXISTS uq_chain_operation_resource;
ALTER TABLE IF EXISTS ONLY public.trades DROP CONSTRAINT IF EXISTS trades_pkey;
ALTER TABLE IF EXISTS ONLY public.retirements DROP CONSTRAINT IF EXISTS retirements_pkey;
ALTER TABLE IF EXISTS ONLY public.projects DROP CONSTRAINT IF EXISTS projects_pkey;
ALTER TABLE IF EXISTS ONLY public.project_documents DROP CONSTRAINT IF EXISTS project_documents_storage_name_key;
ALTER TABLE IF EXISTS ONLY public.project_documents DROP CONSTRAINT IF EXISTS project_documents_pkey;
ALTER TABLE IF EXISTS ONLY public.password_reset_tokens DROP CONSTRAINT IF EXISTS password_reset_tokens_pkey;
ALTER TABLE IF EXISTS ONLY public.operation_requests DROP CONSTRAINT IF EXISTS operation_requests_pkey;
ALTER TABLE IF EXISTS ONLY public.listings DROP CONSTRAINT IF EXISTS listings_pkey;
ALTER TABLE IF EXISTS ONLY public.ledger_entries DROP CONSTRAINT IF EXISTS ledger_entries_pkey;
ALTER TABLE IF EXISTS ONLY public.holdings DROP CONSTRAINT IF EXISTS holdings_pkey;
ALTER TABLE IF EXISTS ONLY public.credit_batches DROP CONSTRAINT IF EXISTS credit_batches_serial_prefix_key;
ALTER TABLE IF EXISTS ONLY public.credit_batches DROP CONSTRAINT IF EXISTS credit_batches_pkey;
ALTER TABLE IF EXISTS ONLY public.chain_operations DROP CONSTRAINT IF EXISTS chain_operations_transaction_hash_key;
ALTER TABLE IF EXISTS ONLY public.chain_operations DROP CONSTRAINT IF EXISTS chain_operations_pkey;
ALTER TABLE IF EXISTS ONLY public.audit_events DROP CONSTRAINT IF EXISTS audit_events_pkey;
ALTER TABLE IF EXISTS ONLY public.alembic_version DROP CONSTRAINT IF EXISTS alembic_version_pkc;
DROP TABLE IF EXISTS public.users;
DROP TABLE IF EXISTS public.trades;
DROP TABLE IF EXISTS public.retirements;
DROP TABLE IF EXISTS public.projects;
DROP TABLE IF EXISTS public.project_documents;
DROP TABLE IF EXISTS public.password_reset_tokens;
DROP TABLE IF EXISTS public.operation_requests;
DROP TABLE IF EXISTS public.listings;
DROP TABLE IF EXISTS public.ledger_entries;
DROP TABLE IF EXISTS public.holdings;
DROP TABLE IF EXISTS public.credit_batches;
DROP TABLE IF EXISTS public.chain_operations;
DROP TABLE IF EXISTS public.audit_events;
DROP TABLE IF EXISTS public.alembic_version;
DROP TYPE IF EXISTS public.role;
DROP TYPE IF EXISTS public.projectstatus;
DROP TYPE IF EXISTS public.listingstatus;
DROP TYPE IF EXISTS public.ledgerkind;
--
-- Name: ledgerkind; Type: TYPE; Schema: public; Owner: carbon
--

CREATE TYPE public.ledgerkind AS ENUM (
    'ISSUE',
    'TRADE_IN',
    'TRADE_OUT',
    'RETIRE'
);


ALTER TYPE public.ledgerkind OWNER TO carbon;

--
-- Name: listingstatus; Type: TYPE; Schema: public; Owner: carbon
--

CREATE TYPE public.listingstatus AS ENUM (
    'OPEN',
    'FILLED',
    'CANCELLED'
);


ALTER TYPE public.listingstatus OWNER TO carbon;

--
-- Name: projectstatus; Type: TYPE; Schema: public; Owner: carbon
--

CREATE TYPE public.projectstatus AS ENUM (
    'DRAFT',
    'PENDING',
    'APPROVED',
    'REJECTED'
);


ALTER TYPE public.projectstatus OWNER TO carbon;

--
-- Name: role; Type: TYPE; Schema: public; Owner: carbon
--

CREATE TYPE public.role AS ENUM (
    'ADMIN',
    'VERIFIER',
    'MEMBER'
);


ALTER TYPE public.role OWNER TO carbon;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: carbon
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO carbon;

--
-- Name: audit_events; Type: TABLE; Schema: public; Owner: carbon
--

CREATE TABLE public.audit_events (
    id character varying(36) NOT NULL,
    actor_id character varying(36),
    action character varying(80) NOT NULL,
    resource_type character varying(40) NOT NULL,
    resource_id character varying(36) NOT NULL,
    detail text NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.audit_events OWNER TO carbon;

--
-- Name: chain_operations; Type: TABLE; Schema: public; Owner: carbon
--

CREATE TABLE public.chain_operations (
    id character varying(36) NOT NULL,
    operation_type character varying(40) NOT NULL,
    resource_type character varying(40) NOT NULL,
    resource_id character varying(36) NOT NULL,
    chain_id integer NOT NULL,
    contract_address character varying(64) NOT NULL,
    payload json NOT NULL,
    status character varying(20) NOT NULL,
    attempts integer NOT NULL,
    transaction_hash character varying(80),
    block_number integer,
    error_message text,
    created_at timestamp with time zone NOT NULL,
    submitted_at timestamp with time zone,
    confirmed_at timestamp with time zone,
    raw_transaction text,
    nonce integer,
    next_attempt_at timestamp with time zone
);


ALTER TABLE public.chain_operations OWNER TO carbon;

--
-- Name: credit_batches; Type: TABLE; Schema: public; Owner: carbon
--

CREATE TABLE public.credit_batches (
    id character varying(36) NOT NULL,
    project_id character varying(36) NOT NULL,
    vintage integer NOT NULL,
    methodology character varying(120) NOT NULL,
    serial_prefix character varying(80) NOT NULL,
    total_issued numeric(20,4) NOT NULL,
    total_retired numeric(20,4) NOT NULL,
    issued_by character varying(36) NOT NULL,
    issued_at timestamp with time zone NOT NULL,
    chain_batch_id integer,
    CONSTRAINT ck_batch_issued_positive CHECK ((total_issued > (0)::numeric)),
    CONSTRAINT ck_batch_retired_valid CHECK (((total_retired >= (0)::numeric) AND (total_retired <= total_issued)))
);


ALTER TABLE public.credit_batches OWNER TO carbon;

--
-- Name: holdings; Type: TABLE; Schema: public; Owner: carbon
--

CREATE TABLE public.holdings (
    id character varying(36) NOT NULL,
    user_id character varying(36) NOT NULL,
    batch_id character varying(36) NOT NULL,
    quantity numeric(20,4) NOT NULL,
    locked_quantity numeric(20,4) NOT NULL,
    version integer NOT NULL,
    CONSTRAINT ck_holding_locked_valid CHECK (((locked_quantity >= (0)::numeric) AND (locked_quantity <= quantity))),
    CONSTRAINT ck_holding_quantity_nonnegative CHECK ((quantity >= (0)::numeric))
);


ALTER TABLE public.holdings OWNER TO carbon;

--
-- Name: ledger_entries; Type: TABLE; Schema: public; Owner: carbon
--

CREATE TABLE public.ledger_entries (
    id character varying(36) NOT NULL,
    user_id character varying(36) NOT NULL,
    batch_id character varying(36) NOT NULL,
    kind public.ledgerkind NOT NULL,
    quantity_delta numeric(20,4) NOT NULL,
    balance_after numeric(20,4) NOT NULL,
    reference_type character varying(30) NOT NULL,
    reference_id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.ledger_entries OWNER TO carbon;

--
-- Name: listings; Type: TABLE; Schema: public; Owner: carbon
--

CREATE TABLE public.listings (
    id character varying(36) NOT NULL,
    seller_id character varying(36) NOT NULL,
    batch_id character varying(36) NOT NULL,
    quantity numeric(20,4) NOT NULL,
    remaining_quantity numeric(20,4) NOT NULL,
    unit_price numeric(20,2) NOT NULL,
    currency character varying(3) NOT NULL,
    status public.listingstatus NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.listings OWNER TO carbon;

--
-- Name: operation_requests; Type: TABLE; Schema: public; Owner: carbon
--

CREATE TABLE public.operation_requests (
    id character varying(36) NOT NULL,
    user_id character varying(36) NOT NULL,
    endpoint character varying(100) NOT NULL,
    key character varying(100) NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.operation_requests OWNER TO carbon;

--
-- Name: password_reset_tokens; Type: TABLE; Schema: public; Owner: carbon
--

CREATE TABLE public.password_reset_tokens (
    id character varying(36) NOT NULL,
    user_id character varying(36) NOT NULL,
    token_hash character varying(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.password_reset_tokens OWNER TO carbon;

--
-- Name: project_documents; Type: TABLE; Schema: public; Owner: carbon
--

CREATE TABLE public.project_documents (
    id character varying(36) NOT NULL,
    project_id character varying(36) NOT NULL,
    uploaded_by character varying(36) NOT NULL,
    category character varying(50) NOT NULL,
    original_name character varying(255) NOT NULL,
    storage_name character varying(255) NOT NULL,
    content_type character varying(120) NOT NULL,
    size_bytes integer NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.project_documents OWNER TO carbon;

--
-- Name: projects; Type: TABLE; Schema: public; Owner: carbon
--

CREATE TABLE public.projects (
    id character varying(36) NOT NULL,
    owner_id character varying(36) NOT NULL,
    name character varying(200) NOT NULL,
    project_type character varying(80) NOT NULL,
    region character varying(120) NOT NULL,
    methodology character varying(120) NOT NULL,
    description text NOT NULL,
    estimated_tonnes numeric(20,4) NOT NULL,
    status public.projectstatus NOT NULL,
    review_note text,
    reviewed_by character varying(36),
    reviewed_at timestamp with time zone,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    chain_token_id integer
);


ALTER TABLE public.projects OWNER TO carbon;

--
-- Name: retirements; Type: TABLE; Schema: public; Owner: carbon
--

CREATE TABLE public.retirements (
    id character varying(36) NOT NULL,
    certificate_no character varying(80) NOT NULL,
    user_id character varying(36) NOT NULL,
    batch_id character varying(36) NOT NULL,
    quantity numeric(20,4) NOT NULL,
    beneficiary character varying(200) NOT NULL,
    reason text NOT NULL,
    retired_at timestamp with time zone NOT NULL,
    transaction_hash character varying(80),
    chain_retirement_id integer
);


ALTER TABLE public.retirements OWNER TO carbon;

--
-- Name: trades; Type: TABLE; Schema: public; Owner: carbon
--

CREATE TABLE public.trades (
    id character varying(36) NOT NULL,
    listing_id character varying(36) NOT NULL,
    buyer_id character varying(36) NOT NULL,
    seller_id character varying(36) NOT NULL,
    batch_id character varying(36) NOT NULL,
    quantity numeric(20,4) NOT NULL,
    unit_price numeric(20,2) NOT NULL,
    total_amount numeric(20,2) NOT NULL,
    currency character varying(3) NOT NULL,
    traded_at timestamp with time zone NOT NULL
);


ALTER TABLE public.trades OWNER TO carbon;

--
-- Name: users; Type: TABLE; Schema: public; Owner: carbon
--

CREATE TABLE public.users (
    id character varying(36) NOT NULL,
    email character varying(320) NOT NULL,
    password_hash character varying(255) NOT NULL,
    display_name character varying(120) NOT NULL,
    role public.role NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    wallet_address character varying(42),
    wallet_nonce character varying(64),
    wallet_nonce_expires_at timestamp with time zone
);


ALTER TABLE public.users OWNER TO carbon;

--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: carbon
--

COPY public.alembic_version (version_num) FROM stdin;
0005
\.


--
-- Data for Name: audit_events; Type: TABLE DATA; Schema: public; Owner: carbon
--

COPY public.audit_events (id, actor_id, action, resource_type, resource_id, detail, created_at) FROM stdin;
6a0e07d6-4b83-4ed1-a3df-b1445ebcff35	0e0f9513-8b90-477e-ba2d-5c4339da013e	project.created	project	15aaac54-7578-447b-a29c-703b4cddacc2	{}	2026-09-24 03:29:11.342867+00
a442672a-a626-4f48-a075-ec5d176bf9b2	0e0f9513-8b90-477e-ba2d-5c4339da013e	project.submitted	project	15aaac54-7578-447b-a29c-703b4cddacc2	{}	2026-09-24 03:29:29.687188+00
f03f3c88-b198-4721-9978-4d0bebd2d0ca	0e0f9513-8b90-477e-ba2d-5c4339da013e	project.reviewed	project	15aaac54-7578-447b-a29c-703b4cddacc2	{"approved": true}	2026-09-24 03:29:45.155317+00
4eba3618-bc7e-436f-9832-21ad82b91a50	0e0f9513-8b90-477e-ba2d-5c4339da013e	credits.issued	batch	a716ad52-8607-4c34-af80-ec34b996bf03	{"quantity": "2600"}	2026-09-24 03:29:55.760764+00
4237a4e6-2867-44a5-9004-345868658f75	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	user.registered	user	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	{}	2026-09-28 03:41:53.184111+00
cb1eb0de-5189-496b-af48-23f105b08f7e	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	project.created	project	d5a0a483-5533-4628-a485-722728a891fe	{}	2026-09-28 05:56:09.680152+00
31b11140-12e5-48cb-96a0-56dfa4e25507	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	project.submitted	project	d5a0a483-5533-4628-a485-722728a891fe	{}	2026-09-28 05:56:13.602258+00
ec512478-3706-4f7b-ab8f-f5ff233c5b98	0e0f9513-8b90-477e-ba2d-5c4339da013e	user.password_reset	user	0e0f9513-8b90-477e-ba2d-5c4339da013e	{}	2026-09-28 06:04:35.275008+00
9e727db7-54f3-490d-a452-f4c422d74873	0e0f9513-8b90-477e-ba2d-5c4339da013e	listing.created	listing	a886c39d-afd1-41f9-83b9-20f031f96e79	{}	2026-09-28 06:05:03.933213+00
7399b302-3fbe-4304-986b-d08e84958d6e	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	trade.settled	trade	68912560-c49d-4bae-ad34-6c7f3b15ccf7	{}	2026-09-28 06:14:27.987945+00
2a06e58e-e345-4105-9e65-8d9987ca0b60	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	credits.retired	retirement	e1f1c553-2453-450a-aefc-4a34e0049988	{}	2026-09-28 06:15:58.372959+00
d267e997-d630-40aa-b96b-fd28267b2072	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	project.created	project	53acd158-eddc-4a20-8393-3320b07b29b0	{}	2026-09-28 07:05:37.530983+00
a5e28804-8fa8-4636-aa10-f640aa50b476	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	project.created	project	527db8c5-814d-4ec9-9a34-58660948b24d	{}	2026-09-28 08:50:46.933466+00
9d404785-a4aa-4036-99ed-94e96e326281	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	wallet.linked	user	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	{"address": "0xF0BBE52E3b1c7893db3466bd7d8e03492Cb1FD1e"}	2026-09-29 08:29:54.769438+00
cdde3e85-7afe-42c9-9966-3962e1a74df1	0e0f9513-8b90-477e-ba2d-5c4339da013e	project.reviewed	project	d5a0a483-5533-4628-a485-722728a891fe	{"approved": true}	2026-09-29 08:31:19.676749+00
73ae9626-15f3-4a6a-b9d0-f4f27ccdf763	0e0f9513-8b90-477e-ba2d-5c4339da013e	credits.issued	batch	535da30a-4705-4e3e-aed1-84104b9053f7	{"quantity": "3000"}	2026-09-29 08:31:27.079518+00
84301f7b-a536-4710-8b56-8edfe8b2326d	0e0f9513-8b90-477e-ba2d-5c4339da013e	wallet.linked	user	0e0f9513-8b90-477e-ba2d-5c4339da013e	{"address": "0x096eD1B4e6375F3D7ec4625D4D66b79EB1e0a36F"}	2026-09-29 08:32:28.748024+00
1013c5b1-d25d-4428-9f75-9676595747f2	0e0f9513-8b90-477e-ba2d-5c4339da013e	project.created	project	1181b492-3537-4c17-960d-86c2f2b03bda	{}	2026-09-29 08:34:03.156138+00
4f93bdca-f75e-43d5-b524-20d915f6b699	0e0f9513-8b90-477e-ba2d-5c4339da013e	project.submitted	project	1181b492-3537-4c17-960d-86c2f2b03bda	{}	2026-09-29 08:34:06.578461+00
db20df47-0da4-43f6-aabe-34383e5ce350	0e0f9513-8b90-477e-ba2d-5c4339da013e	project.reviewed	project	1181b492-3537-4c17-960d-86c2f2b03bda	{"approved": true}	2026-09-29 08:34:13.142362+00
0f53345e-ac3c-4fa1-927b-6b658401683a	0e0f9513-8b90-477e-ba2d-5c4339da013e	credits.issued	batch	8f0a62b6-556d-4b84-b612-74ac65a68569	{"quantity": "3000"}	2026-09-29 08:34:19.156021+00
\.


--
-- Data for Name: chain_operations; Type: TABLE DATA; Schema: public; Owner: carbon
--

COPY public.chain_operations (id, operation_type, resource_type, resource_id, chain_id, contract_address, payload, status, attempts, transaction_hash, block_number, error_message, created_at, submitted_at, confirmed_at, raw_transaction, nonce, next_attempt_at) FROM stdin;
d81d0384-ce69-4924-9c3f-cbd6c35816c0	project.register	project	15aaac54-7578-447b-a29c-703b4cddacc2	43113	0x590FcD85a12B9D6B00E6a38A3A72c84Ec08303c2	{"project_id": "15aaac54-7578-447b-a29c-703b4cddacc2", "owner_id": "0e0f9513-8b90-477e-ba2d-5c4339da013e", "name": "\\u534e\\u5357\\u5149\\u4f0f\\u4e00\\u671f", "methodology": "CM-001-V01", "region": "\\u5e7f\\u4e1c"}	confirmed	1	0x66c575babe687154c33ed0a09c55e68d6ffaa2ee24333c6d6d8efd67ab2ce5df	58804908	\N	2026-09-24 03:29:45.157302+00	2026-09-28 03:26:11.33248+00	2026-09-28 03:26:22.580657+00	0xf901aa0281a08303c10794590fcd85a12b9d6b00e6a38a3a72c84ec08303c280b901449b3041d00000000000000000000000008b6de89327bb6cdceae286a34f54b9bc6773eb610000000000000000000000000000000000000000000000000000000000000080ef4ea26a52a4e256d45eebfa6885ad5995c111fd54cff950b61c0146cd5d4ca100000000000000000000000000000000000000000000000000000000000000e0000000000000000000000000000000000000000000000000000000000000002431356161616335342d373537382d343437622d613239632d373033623463646461636332000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000039636172626f6e6c696e6b3a2f2f70726f6a6563742f31356161616335342d373537382d343437622d613239632d37303362346364646163633200000000000000830150f5a0cedb9f9b730b2abff9a22d2bb1c106eb0054dd63e2c41da942f02160ecc5db7ea006f439eab34dd1240c58bb0e656fcca53957e38c58a3d5bb1fac64a42fdd0234	2	\N
86409a5e-1a57-4f0f-af0c-52ffddb1a27e	credit.issue	batch	a716ad52-8607-4c34-af80-ec34b996bf03	43113	0xD979f63A0EC1540c5a551304f120bAa82CdaCe1D	{"batch_id": "a716ad52-8607-4c34-af80-ec34b996bf03", "project_id": "15aaac54-7578-447b-a29c-703b4cddacc2", "vintage": 2026, "quantity": "2600", "serial_prefix": "CL-2026-0722E09966"}	confirmed	1	0xc6906aaf4736509abae8e0c3acbe3ad1d15d44de7a12dd8edbef3a379bdf7bbd	58804914	\N	2026-09-24 03:29:55.761227+00	2026-09-28 03:26:24.809031+00	2026-09-28 03:26:30.92603+00	0xf901aa0381a0830449c594d979f63a0ec1540c5a551304f120baa82cdace1d80b90144a02645490000000000000000000000008b6de89327bb6cdceae286a34f54b9bc6773eb610000000000000000000000000000000000000000000000000000000000000001945dcd9b3e789db3a2c2ecd4b741ba96d405780ca6ca2c946d3d42ad3f60bffe00000000000000000000000000000000000000000000000000000000000007ea00000000000000000000000000000000000000000000000000000000018cba80e25fe1da8cebffc162f710b0ab987e7450e9536be8344d85084d5273ac00cfce00000000000000000000000000000000000000000000000000000000000000e00000000000000000000000000000000000000000000000000000000000000037636172626f6e6c696e6b3a2f2f62617463682f61373136616435322d383630372d346333342d616638302d656333346239393662663033000000000000000000830150f5a0d8e6d8142560a5b51ff0a375eea3c2c4e7106a497f477f20f4cebc87b9dba7a5a00a822743344a66262e89b1c5c8e7c90f874cef79f25ff5021fbeb9aae11b443a	3	\N
dc281a11-bac3-4b18-8d0d-e07438c42a72	credit.retire	retirement	e1f1c553-2453-450a-aefc-4a34e0049988	43113	0xD979f63A0EC1540c5a551304f120bAa82CdaCe1D	{"retirement_id": "e1f1c553-2453-450a-aefc-4a34e0049988", "batch_id": "a716ad52-8607-4c34-af80-ec34b996bf03", "quantity": "100", "beneficiary": "\\u65b0\\u8bda\\u94a2\\u94c1\\u5382", "reason": "2026\\u5e74\\u8fd0\\u8425\\u6392\\u653e\\u62b5\\u6d88"}	confirmed	1	0x7aa023b6d5c0e9cb021320ca91e9d951722fe5e4239f1e3c57c21973a200ecfa	58809128	\N	2026-09-28 06:15:58.37404+00	2026-09-28 06:16:00.714565+00	2026-09-28 06:16:08.547804+00	0xf8e90481a083031e9c94d979f63a0ec1540c5a551304f120baa82cdace1d80b884318521c9000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000f4240c9836df4db5618f1ee906d09cda3915579ceaa89d3670c78c2bdbf11b2e3683000cb66bc9bdd1e50ed5112ace83d17b8ecc64bcc65c567dcc83ce42e8dbdfe24830150f5a02adf64d9ab6f410b9e6cb169f0e757209dfa90d3443dce59daa2b37da4e87850a02972f9deb27a9f953dff1f0a9a4271b9a71861551aae4b079c435fc6d5023c0b	4	\N
7365ecb8-f2e3-4837-966d-834d7112b8f1	project.register	project	d5a0a483-5533-4628-a485-722728a891fe	43113	0x590FcD85a12B9D6B00E6a38A3A72c84Ec08303c2	{"project_id": "d5a0a483-5533-4628-a485-722728a891fe", "owner_id": "a74207e5-9d93-4ca3-ad5d-f70f01b1f551", "owner_wallet": "0xF0BBE52E3b1c7893db3466bd7d8e03492Cb1FD1e", "name": "\\u534e\\u5317\\u5149\\u7535\\u4e00\\u671f", "methodology": "CM-001-V01", "region": "\\u6cb3\\u5317"}	confirmed	1	0x9a410bc1be3646744d1f90518116473fdbf795304aaaafb6952e2983cb2097a3	58847669	\N	2026-09-29 08:31:19.679227+00	2026-09-29 08:31:22.034407+00	2026-09-29 08:31:33.384513+00	0xf901aa0581a08303cadf94590fcd85a12b9d6b00e6a38a3a72c84ec08303c280b901449b3041d0000000000000000000000000f0bbe52e3b1c7893db3466bd7d8e03492cb1fd1e00000000000000000000000000000000000000000000000000000000000000801ff4e61cabd9e3655fd8a18c40e469115c3449f1f833ae565dd24b6dafce6d8300000000000000000000000000000000000000000000000000000000000000e0000000000000000000000000000000000000000000000000000000000000002464356130613438332d353533332d343632382d613438352d373232373238613839316665000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000039636172626f6e6c696e6b3a2f2f70726f6a6563742f64356130613438332d353533332d343632382d613438352d37323237323861383931666500000000000000830150f6a04b3e4a51bae30e814d87296beb2476d93706504ddaad60cfc1ec06000354423ca02e53ae15c76c7c2f754b9bc489e9ae8475eac40674508c11e28936f45fda88b9	5	\N
927a9f9e-c80c-4ef1-b8ec-3c4675d03fc6	credit.issue	batch	535da30a-4705-4e3e-aed1-84104b9053f7	43113	0xD979f63A0EC1540c5a551304f120bAa82CdaCe1D	{"batch_id": "535da30a-4705-4e3e-aed1-84104b9053f7", "project_id": "d5a0a483-5533-4628-a485-722728a891fe", "recipient": "0xF0BBE52E3b1c7893db3466bd7d8e03492Cb1FD1e", "vintage": 2026, "quantity": "3000", "serial_prefix": "CL-2026-A02D67F054"}	confirmed	1	0x32542a6cbc746837ba761e931b848a58a70839dbef7cde1f22a4cf7a59c1723c	58847677	\N	2026-09-29 08:31:27.079929+00	2026-09-29 08:31:37.307278+00	2026-09-29 08:31:45.005725+00	0xf901aa0681a08304539d94d979f63a0ec1540c5a551304f120baa82cdace1d80b90144a0264549000000000000000000000000f0bbe52e3b1c7893db3466bd7d8e03492cb1fd1e000000000000000000000000000000000000000000000000000000000000000210df427c7a7884d4e883959653d1769e3383248692c3d5e6dceeba8bd693376200000000000000000000000000000000000000000000000000000000000007ea0000000000000000000000000000000000000000000000000000000001c9c380c9ab5592dfd87c83f6874150c453008a22d002cf840d93c4682406f8be988f0100000000000000000000000000000000000000000000000000000000000000e00000000000000000000000000000000000000000000000000000000000000037636172626f6e6c696e6b3a2f2f62617463682f35333564613330612d343730352d346533652d616564312d383431303462393035336637000000000000000000830150f5a0076c1db5889d806cbfc100a315ccc13172e52ce69b1030102b4161dad5c5e035a01dda688790a7c0764ece1f16c77497c1e1cbf7a3e2392a5971f7b1166ef85f09	6	\N
27aa48c9-3c54-494c-b69e-5d4cec7e2a11	project.register	project	1181b492-3537-4c17-960d-86c2f2b03bda	43113	0x590FcD85a12B9D6B00E6a38A3A72c84Ec08303c2	{"project_id": "1181b492-3537-4c17-960d-86c2f2b03bda", "owner_id": "0e0f9513-8b90-477e-ba2d-5c4339da013e", "owner_wallet": "0x096eD1B4e6375F3D7ec4625D4D66b79EB1e0a36F", "name": "\\u5317\\u4eac\\u5927\\u5174\\u7f8e\\u5fc3\\u5149\\u4f0f", "methodology": "CM-001-V01", "region": "\\u5317\\u4eac"}	confirmed	1	0x44509d91d81447a85b2aed2e45922195cbf054d03d84b792ed54aef41f44c45f	58847735	\N	2026-09-29 08:34:13.142889+00	2026-09-29 08:34:18.890266+00	2026-09-29 08:34:25.710915+00	0xf901aa0781a08303cadf94590fcd85a12b9d6b00e6a38a3a72c84ec08303c280b901449b3041d0000000000000000000000000096ed1b4e6375f3d7ec4625d4d66b79eb1e0a36f0000000000000000000000000000000000000000000000000000000000000080e885b5344391f736d4f61a509d99b36e8e595731471ccda633467d43454c07c200000000000000000000000000000000000000000000000000000000000000e0000000000000000000000000000000000000000000000000000000000000002431313831623439322d333533372d346331372d393630642d383663326632623033626461000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000039636172626f6e6c696e6b3a2f2f70726f6a6563742f31313831623439322d333533372d346331372d393630642d38366332663262303362646100000000000000830150f6a0c15c8fa5a96341ac3c9459930cff870141889f683d23ed7658ab5b0df9107e3ba05615c48cde9ca15fdeb7e69e055e77a8c96d961305e3f8a5b189f47f938181f6	7	\N
64671113-f235-43cc-89d5-15d926b4f874	credit.issue	batch	8f0a62b6-556d-4b84-b612-74ac65a68569	43113	0xD979f63A0EC1540c5a551304f120bAa82CdaCe1D	{"batch_id": "8f0a62b6-556d-4b84-b612-74ac65a68569", "project_id": "1181b492-3537-4c17-960d-86c2f2b03bda", "recipient": "0x096eD1B4e6375F3D7ec4625D4D66b79EB1e0a36F", "vintage": 2026, "quantity": "3000", "serial_prefix": "CL-2026-D645D8D48B"}	confirmed	1	0x7cf42a343aca67d8a4aa85112916aacd4f6af11ee03d857c17b86e1cc3f24dc5	58847743	\N	2026-09-29 08:34:19.15645+00	2026-09-29 08:34:30.196753+00	2026-09-29 08:34:35.598486+00	0xf901aa0881a08304539d94d979f63a0ec1540c5a551304f120baa82cdace1d80b90144a0264549000000000000000000000000096ed1b4e6375f3d7ec4625d4d66b79eb1e0a36f00000000000000000000000000000000000000000000000000000000000000031697c0a8866af6c31664df17e4a74b5365b57ccbc999dc004ed964eabbe35a4500000000000000000000000000000000000000000000000000000000000007ea0000000000000000000000000000000000000000000000000000000001c9c3800cc99d203f62d8785bb7f1a7640a44f8d3fdc0aac13ff6240b3e79afedf0692400000000000000000000000000000000000000000000000000000000000000e00000000000000000000000000000000000000000000000000000000000000037636172626f6e6c696e6b3a2f2f62617463682f38663061363262362d353536642d346238342d623631322d373461633635613638353639000000000000000000830150f6a0b31ca300653d7528fed90256596be23ee8688313ac55687f0125046f3a6ddb50a023b86297d54cdb06b1ff478ad4e97c0bc7fcf6fe416b1c7e1548820445a1a75d	8	\N
\.


--
-- Data for Name: credit_batches; Type: TABLE DATA; Schema: public; Owner: carbon
--

COPY public.credit_batches (id, project_id, vintage, methodology, serial_prefix, total_issued, total_retired, issued_by, issued_at, chain_batch_id) FROM stdin;
a716ad52-8607-4c34-af80-ec34b996bf03	15aaac54-7578-447b-a29c-703b4cddacc2	2026	CM-001-V01	CL-2026-0722E09966	2600.0000	100.0000	0e0f9513-8b90-477e-ba2d-5c4339da013e	2026-09-24 03:29:55.753451+00	\N
535da30a-4705-4e3e-aed1-84104b9053f7	d5a0a483-5533-4628-a485-722728a891fe	2026	CM-001-V01	CL-2026-A02D67F054	3000.0000	0.0000	0e0f9513-8b90-477e-ba2d-5c4339da013e	2026-09-29 08:31:27.075406+00	2
8f0a62b6-556d-4b84-b612-74ac65a68569	1181b492-3537-4c17-960d-86c2f2b03bda	2026	CM-001-V01	CL-2026-D645D8D48B	3000.0000	0.0000	0e0f9513-8b90-477e-ba2d-5c4339da013e	2026-09-29 08:34:19.154963+00	3
\.


--
-- Data for Name: holdings; Type: TABLE DATA; Schema: public; Owner: carbon
--

COPY public.holdings (id, user_id, batch_id, quantity, locked_quantity, version) FROM stdin;
79cf2c0f-9794-4cfe-8fbf-b6c21bc0c0d4	0e0f9513-8b90-477e-ba2d-5c4339da013e	a716ad52-8607-4c34-af80-ec34b996bf03	2500.0000	1900.0000	1
cb86a66c-ab5d-4343-bc0c-0fdda9dd0a9e	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	a716ad52-8607-4c34-af80-ec34b996bf03	0.0000	0.0000	1
\.


--
-- Data for Name: ledger_entries; Type: TABLE DATA; Schema: public; Owner: carbon
--

COPY public.ledger_entries (id, user_id, batch_id, kind, quantity_delta, balance_after, reference_type, reference_id, created_at) FROM stdin;
03ce69ce-b99a-470c-812d-057f10112eca	0e0f9513-8b90-477e-ba2d-5c4339da013e	a716ad52-8607-4c34-af80-ec34b996bf03	ISSUE	2600.0000	2600.0000	batch	a716ad52-8607-4c34-af80-ec34b996bf03	2026-09-24 03:29:55.763025+00
232439e4-35e3-45be-b8d4-4a8b6010f4b0	0e0f9513-8b90-477e-ba2d-5c4339da013e	a716ad52-8607-4c34-af80-ec34b996bf03	TRADE_OUT	-100.0000	2500.0000	trade	68912560-c49d-4bae-ad34-6c7f3b15ccf7	2026-09-28 06:14:27.989522+00
55cdb867-4117-4c93-a2d9-54b5eea740b4	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	a716ad52-8607-4c34-af80-ec34b996bf03	TRADE_IN	100.0000	100.0000	trade	68912560-c49d-4bae-ad34-6c7f3b15ccf7	2026-09-28 06:14:27.989529+00
e4e463e2-d33a-4e78-918b-23ef149cf389	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	a716ad52-8607-4c34-af80-ec34b996bf03	RETIRE	-100.0000	0.0000	retirement	e1f1c553-2453-450a-aefc-4a34e0049988	2026-09-28 06:15:58.37518+00
\.


--
-- Data for Name: listings; Type: TABLE DATA; Schema: public; Owner: carbon
--

COPY public.listings (id, seller_id, batch_id, quantity, remaining_quantity, unit_price, currency, status, created_at, updated_at) FROM stdin;
a886c39d-afd1-41f9-83b9-20f031f96e79	0e0f9513-8b90-477e-ba2d-5c4339da013e	a716ad52-8607-4c34-af80-ec34b996bf03	2000.0000	1900.0000	100.00	CNY	OPEN	2026-09-28 06:05:03.9304+00	2026-09-28 06:14:27.984594+00
\.


--
-- Data for Name: operation_requests; Type: TABLE DATA; Schema: public; Owner: carbon
--

COPY public.operation_requests (id, user_id, endpoint, key, created_at) FROM stdin;
7c93c468-37b6-4278-af7c-0e3d09009993	0e0f9513-8b90-477e-ba2d-5c4339da013e	credits.issue	a1770d67-955f-40d5-999f-9da772c90ab2	2026-09-24 03:29:55.751377+00
94fb1031-c97d-42be-84c3-e3be85ba33e3	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	listing.buy:a886c39d-afd1-41f9-83b9-20f031f96e79	24242c17-99ff-496c-9b6b-124be04f1859	2026-09-28 06:14:27.97801+00
181aa278-bc02-4315-a8c3-a1603be9827a	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	credits.retire	279f60c8-4b47-4c41-be2c-eb08a2cc73b6	2026-09-28 06:15:58.367424+00
fe3b3ae9-5b0b-4c37-bbb2-5a50f90420b4	0e0f9513-8b90-477e-ba2d-5c4339da013e	credits.issue	ad3eca3c-3394-415f-82a2-8b4bf82c4ca1	2026-09-29 08:31:27.072259+00
cadfc74d-3661-4784-a454-3ea4544a4344	0e0f9513-8b90-477e-ba2d-5c4339da013e	credits.issue	253334d9-7629-4f09-a8c8-4e991ff6368e	2026-09-29 08:34:19.153299+00
\.


--
-- Data for Name: password_reset_tokens; Type: TABLE DATA; Schema: public; Owner: carbon
--

COPY public.password_reset_tokens (id, user_id, token_hash, expires_at, used_at, created_at) FROM stdin;
498b6f7a-5e24-4ab6-9218-63a6590bfcef	0e0f9513-8b90-477e-ba2d-5c4339da013e	bc6835b148aa51837e7025477dee82d0ebe77af34f1e24eb7a0746a24041ea5f	2026-09-28 06:34:21.912879+00	2026-09-28 06:04:35.273725+00	2026-09-28 06:04:21.91406+00
\.


--
-- Data for Name: project_documents; Type: TABLE DATA; Schema: public; Owner: carbon
--

COPY public.project_documents (id, project_id, uploaded_by, category, original_name, storage_name, content_type, size_bytes, created_at) FROM stdin;
\.


--
-- Data for Name: projects; Type: TABLE DATA; Schema: public; Owner: carbon
--

COPY public.projects (id, owner_id, name, project_type, region, methodology, description, estimated_tonnes, status, review_note, reviewed_by, reviewed_at, created_at, updated_at, chain_token_id) FROM stdin;
15aaac54-7578-447b-a29c-703b4cddacc2	0e0f9513-8b90-477e-ba2d-5c4339da013e	华南光伏一期	forestry	广东	CM-001-V01		300.0000	APPROVED	准许发放	0e0f9513-8b90-477e-ba2d-5c4339da013e	2026-09-24 03:29:45.155027+00	2026-09-24 03:29:11.338764+00	2026-09-24 03:29:45.161998+00	\N
53acd158-eddc-4a20-8393-3320b07b29b0	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	天津北上光伏能源项目	renewable_energy	天津市	CM-001-V01	123	100.0000	DRAFT	\N	\N	\N	2026-09-28 07:05:37.527814+00	2026-09-28 07:05:37.527817+00	\N
527db8c5-814d-4ec9-9a34-58660948b24d	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	华北林业一期	forestry	河北沧州	CM-001-V01	林场再造林项目，经营面积约3000平方米，主要树种为松树。	2600.0000	DRAFT	\N	\N	\N	2026-09-28 08:50:46.927089+00	2026-09-28 08:50:46.927092+00	\N
d5a0a483-5533-4628-a485-722728a891fe	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	华北光电一期	forestry	河北	CM-001-V01		1300.0000	APPROVED	tongguo 	0e0f9513-8b90-477e-ba2d-5c4339da013e	2026-09-29 08:31:19.675874+00	2026-09-28 05:56:09.67603+00	2026-09-29 08:31:34.185118+00	2
1181b492-3537-4c17-960d-86c2f2b03bda	0e0f9513-8b90-477e-ba2d-5c4339da013e	北京大兴美心光伏	renewable_energy	北京	CM-001-V01	北京大兴	3000.0000	APPROVED	通过	0e0f9513-8b90-477e-ba2d-5c4339da013e	2026-09-29 08:34:13.142069+00	2026-09-29 08:34:03.155253+00	2026-09-29 08:34:26.811661+00	3
\.


--
-- Data for Name: retirements; Type: TABLE DATA; Schema: public; Owner: carbon
--

COPY public.retirements (id, certificate_no, user_id, batch_id, quantity, beneficiary, reason, retired_at, transaction_hash, chain_retirement_id) FROM stdin;
e1f1c553-2453-450a-aefc-4a34e0049988	CLR-20260928-7CE60AE9DC24	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	a716ad52-8607-4c34-af80-ec34b996bf03	100.0000	新诚钢铁厂	2026年运营排放抵消	2026-09-28 06:15:58.371059+00	\N	\N
\.


--
-- Data for Name: trades; Type: TABLE DATA; Schema: public; Owner: carbon
--

COPY public.trades (id, listing_id, buyer_id, seller_id, batch_id, quantity, unit_price, total_amount, currency, traded_at) FROM stdin;
68912560-c49d-4bae-ad34-6c7f3b15ccf7	a886c39d-afd1-41f9-83b9-20f031f96e79	a74207e5-9d93-4ca3-ad5d-f70f01b1f551	0e0f9513-8b90-477e-ba2d-5c4339da013e	a716ad52-8607-4c34-af80-ec34b996bf03	100.0000	100.00	10000.00	CNY	2026-09-28 06:14:27.985634+00
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: carbon
--

COPY public.users (id, email, password_hash, display_name, role, is_active, created_at, wallet_address, wallet_nonce, wallet_nonce_expires_at) FROM stdin;
a74207e5-9d93-4ca3-ad5d-f70f01b1f551	admin@carbon.com	$argon2id$v=19$m=65536,t=3,p=4$B5QCiWKvJbhIty81PWOc/g$PRoEJG14Ca0RsEudqT36aaFDx0qeuM0h/ZHIy0/SMHk	admin	MEMBER	t	2026-09-28 03:41:53.177028+00	0xF0BBE52E3b1c7893db3466bd7d8e03492Cb1FD1e	\N	\N
0e0f9513-8b90-477e-ba2d-5c4339da013e	admin@example.com	$argon2id$v=19$m=65536,t=3,p=4$ulrBSeoexp4Dun/BkvEPsg$Oy6x/cekWrNH5Ri2iCmtGLg8op8HyqvzLKeAmYocjIo	System Administrator	ADMIN	t	2026-09-24 03:00:04.999448+00	0x096eD1B4e6375F3D7ec4625D4D66b79EB1e0a36F	\N	\N
\.


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: audit_events audit_events_pkey; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_pkey PRIMARY KEY (id);


--
-- Name: chain_operations chain_operations_pkey; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.chain_operations
    ADD CONSTRAINT chain_operations_pkey PRIMARY KEY (id);


--
-- Name: chain_operations chain_operations_transaction_hash_key; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.chain_operations
    ADD CONSTRAINT chain_operations_transaction_hash_key UNIQUE (transaction_hash);


--
-- Name: credit_batches credit_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.credit_batches
    ADD CONSTRAINT credit_batches_pkey PRIMARY KEY (id);


--
-- Name: credit_batches credit_batches_serial_prefix_key; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.credit_batches
    ADD CONSTRAINT credit_batches_serial_prefix_key UNIQUE (serial_prefix);


--
-- Name: holdings holdings_pkey; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.holdings
    ADD CONSTRAINT holdings_pkey PRIMARY KEY (id);


--
-- Name: ledger_entries ledger_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.ledger_entries
    ADD CONSTRAINT ledger_entries_pkey PRIMARY KEY (id);


--
-- Name: listings listings_pkey; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.listings
    ADD CONSTRAINT listings_pkey PRIMARY KEY (id);


--
-- Name: operation_requests operation_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.operation_requests
    ADD CONSTRAINT operation_requests_pkey PRIMARY KEY (id);


--
-- Name: password_reset_tokens password_reset_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (id);


--
-- Name: project_documents project_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.project_documents
    ADD CONSTRAINT project_documents_pkey PRIMARY KEY (id);


--
-- Name: project_documents project_documents_storage_name_key; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.project_documents
    ADD CONSTRAINT project_documents_storage_name_key UNIQUE (storage_name);


--
-- Name: projects projects_pkey; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (id);


--
-- Name: retirements retirements_pkey; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.retirements
    ADD CONSTRAINT retirements_pkey PRIMARY KEY (id);


--
-- Name: trades trades_pkey; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_pkey PRIMARY KEY (id);


--
-- Name: chain_operations uq_chain_operation_resource; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.chain_operations
    ADD CONSTRAINT uq_chain_operation_resource UNIQUE (operation_type, resource_id);


--
-- Name: credit_batches uq_credit_batches_chain_batch_id; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.credit_batches
    ADD CONSTRAINT uq_credit_batches_chain_batch_id UNIQUE (chain_batch_id);


--
-- Name: operation_requests uq_operation_request; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.operation_requests
    ADD CONSTRAINT uq_operation_request UNIQUE (user_id, endpoint, key);


--
-- Name: credit_batches uq_project_vintage; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.credit_batches
    ADD CONSTRAINT uq_project_vintage UNIQUE (project_id, vintage);


--
-- Name: projects uq_projects_chain_token_id; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT uq_projects_chain_token_id UNIQUE (chain_token_id);


--
-- Name: retirements uq_retirements_chain_id; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.retirements
    ADD CONSTRAINT uq_retirements_chain_id UNIQUE (chain_retirement_id);


--
-- Name: retirements uq_retirements_transaction_hash; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.retirements
    ADD CONSTRAINT uq_retirements_transaction_hash UNIQUE (transaction_hash);


--
-- Name: holdings uq_user_batch; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.holdings
    ADD CONSTRAINT uq_user_batch UNIQUE (user_id, batch_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_audit_events_action; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_audit_events_action ON public.audit_events USING btree (action);


--
-- Name: ix_audit_events_actor_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_audit_events_actor_id ON public.audit_events USING btree (actor_id);


--
-- Name: ix_audit_events_resource_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_audit_events_resource_id ON public.audit_events USING btree (resource_id);


--
-- Name: ix_chain_operation_status_created; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_chain_operation_status_created ON public.chain_operations USING btree (status, created_at);


--
-- Name: ix_chain_operations_next_attempt_at; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_chain_operations_next_attempt_at ON public.chain_operations USING btree (next_attempt_at);


--
-- Name: ix_chain_operations_resource_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_chain_operations_resource_id ON public.chain_operations USING btree (resource_id);


--
-- Name: ix_chain_operations_status; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_chain_operations_status ON public.chain_operations USING btree (status);


--
-- Name: ix_credit_batches_project_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_credit_batches_project_id ON public.credit_batches USING btree (project_id);


--
-- Name: ix_holdings_batch_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_holdings_batch_id ON public.holdings USING btree (batch_id);


--
-- Name: ix_holdings_user_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_holdings_user_id ON public.holdings USING btree (user_id);


--
-- Name: ix_ledger_entries_batch_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_ledger_entries_batch_id ON public.ledger_entries USING btree (batch_id);


--
-- Name: ix_ledger_entries_created_at; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_ledger_entries_created_at ON public.ledger_entries USING btree (created_at);


--
-- Name: ix_ledger_entries_reference_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_ledger_entries_reference_id ON public.ledger_entries USING btree (reference_id);


--
-- Name: ix_ledger_entries_user_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_ledger_entries_user_id ON public.ledger_entries USING btree (user_id);


--
-- Name: ix_ledger_user_created; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_ledger_user_created ON public.ledger_entries USING btree (user_id, created_at);


--
-- Name: ix_listings_batch_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_listings_batch_id ON public.listings USING btree (batch_id);


--
-- Name: ix_listings_seller_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_listings_seller_id ON public.listings USING btree (seller_id);


--
-- Name: ix_listings_status; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_listings_status ON public.listings USING btree (status);


--
-- Name: ix_operation_requests_user_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_operation_requests_user_id ON public.operation_requests USING btree (user_id);


--
-- Name: ix_password_reset_tokens_expires_at; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_password_reset_tokens_expires_at ON public.password_reset_tokens USING btree (expires_at);


--
-- Name: ix_password_reset_tokens_token_hash; Type: INDEX; Schema: public; Owner: carbon
--

CREATE UNIQUE INDEX ix_password_reset_tokens_token_hash ON public.password_reset_tokens USING btree (token_hash);


--
-- Name: ix_password_reset_tokens_user_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_password_reset_tokens_user_id ON public.password_reset_tokens USING btree (user_id);


--
-- Name: ix_project_document_project_category; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_project_document_project_category ON public.project_documents USING btree (project_id, category);


--
-- Name: ix_project_documents_project_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_project_documents_project_id ON public.project_documents USING btree (project_id);


--
-- Name: ix_project_documents_uploaded_by; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_project_documents_uploaded_by ON public.project_documents USING btree (uploaded_by);


--
-- Name: ix_projects_owner_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_projects_owner_id ON public.projects USING btree (owner_id);


--
-- Name: ix_projects_status; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_projects_status ON public.projects USING btree (status);


--
-- Name: ix_retirements_batch_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_retirements_batch_id ON public.retirements USING btree (batch_id);


--
-- Name: ix_retirements_certificate_no; Type: INDEX; Schema: public; Owner: carbon
--

CREATE UNIQUE INDEX ix_retirements_certificate_no ON public.retirements USING btree (certificate_no);


--
-- Name: ix_retirements_user_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_retirements_user_id ON public.retirements USING btree (user_id);


--
-- Name: ix_trades_buyer_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_trades_buyer_id ON public.trades USING btree (buyer_id);


--
-- Name: ix_trades_listing_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_trades_listing_id ON public.trades USING btree (listing_id);


--
-- Name: ix_trades_seller_id; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_trades_seller_id ON public.trades USING btree (seller_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: carbon
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_role; Type: INDEX; Schema: public; Owner: carbon
--

CREATE INDEX ix_users_role ON public.users USING btree (role);


--
-- Name: ix_users_wallet_address; Type: INDEX; Schema: public; Owner: carbon
--

CREATE UNIQUE INDEX ix_users_wallet_address ON public.users USING btree (wallet_address);


--
-- Name: audit_events audit_events_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id);


--
-- Name: credit_batches credit_batches_issued_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.credit_batches
    ADD CONSTRAINT credit_batches_issued_by_fkey FOREIGN KEY (issued_by) REFERENCES public.users(id);


--
-- Name: credit_batches credit_batches_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.credit_batches
    ADD CONSTRAINT credit_batches_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id);


--
-- Name: holdings holdings_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.holdings
    ADD CONSTRAINT holdings_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.credit_batches(id);


--
-- Name: holdings holdings_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.holdings
    ADD CONSTRAINT holdings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: ledger_entries ledger_entries_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.ledger_entries
    ADD CONSTRAINT ledger_entries_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.credit_batches(id);


--
-- Name: ledger_entries ledger_entries_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.ledger_entries
    ADD CONSTRAINT ledger_entries_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: listings listings_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.listings
    ADD CONSTRAINT listings_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.credit_batches(id);


--
-- Name: listings listings_seller_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.listings
    ADD CONSTRAINT listings_seller_id_fkey FOREIGN KEY (seller_id) REFERENCES public.users(id);


--
-- Name: operation_requests operation_requests_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.operation_requests
    ADD CONSTRAINT operation_requests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: password_reset_tokens password_reset_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: project_documents project_documents_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.project_documents
    ADD CONSTRAINT project_documents_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: project_documents project_documents_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.project_documents
    ADD CONSTRAINT project_documents_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.users(id);


--
-- Name: projects projects_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id);


--
-- Name: projects projects_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(id);


--
-- Name: retirements retirements_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.retirements
    ADD CONSTRAINT retirements_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.credit_batches(id);


--
-- Name: retirements retirements_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.retirements
    ADD CONSTRAINT retirements_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: trades trades_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.credit_batches(id);


--
-- Name: trades trades_buyer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_buyer_id_fkey FOREIGN KEY (buyer_id) REFERENCES public.users(id);


--
-- Name: trades trades_listing_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_listing_id_fkey FOREIGN KEY (listing_id) REFERENCES public.listings(id);


--
-- Name: trades trades_seller_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: carbon
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_seller_id_fkey FOREIGN KEY (seller_id) REFERENCES public.users(id);


--
-- PostgreSQL database dump complete
--

\unrestrict 3YIhccVverWjg4Qe0bHjlcypDW3ZD917Woj1pjBZLhMbTVnPWriVIUNt1WwvcfQ

