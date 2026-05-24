--
-- PostgreSQL database dump
--

\restrict Fc65oD2b5Vcq5DUI21TaruwADIzUUNEwQBkmW9ZJTTcIyiIv5EdUM3sni0r22p5

-- Dumped from database version 18.0
-- Dumped by pg_dump version 18.0

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: cat_metodo_aplicacion; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cat_metodo_aplicacion (
    id_metodoaplicacion integer NOT NULL,
    nombre_metodoaplicacion character varying NOT NULL
);


ALTER TABLE public.cat_metodo_aplicacion OWNER TO postgres;

--
-- Name: cat_metodo_aplicacion_id_metodoaplicacion_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.cat_metodo_aplicacion_id_metodoaplicacion_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.cat_metodo_aplicacion_id_metodoaplicacion_seq OWNER TO postgres;

--
-- Name: cat_metodo_aplicacion_id_metodoaplicacion_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.cat_metodo_aplicacion_id_metodoaplicacion_seq OWNED BY public.cat_metodo_aplicacion.id_metodoaplicacion;


--
-- Name: cat_tipo_insumo; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cat_tipo_insumo (
    id_tipoinsumo character varying NOT NULL,
    nombre_tipo character varying NOT NULL
);


ALTER TABLE public.cat_tipo_insumo OWNER TO postgres;

--
-- Name: cat_unidad_medida; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cat_unidad_medida (
    id_unidadmedida integer NOT NULL,
    nombre_unidadmedida character varying NOT NULL
);


ALTER TABLE public.cat_unidad_medida OWNER TO postgres;

--
-- Name: cat_unidad_medida_id_unidadmedida_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.cat_unidad_medida_id_unidadmedida_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.cat_unidad_medida_id_unidadmedida_seq OWNER TO postgres;

--
-- Name: cat_unidad_medida_id_unidadmedida_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.cat_unidad_medida_id_unidadmedida_seq OWNED BY public.cat_unidad_medida.id_unidadmedida;


--
-- Name: pago; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.pago (
    id_pago character varying NOT NULL,
    fecha_pago date NOT NULL,
    preciokilo_pago numeric(10,2),
    estado_pago boolean,
    monto_pago numeric(10,2),
    metodo_pago character varying(50),
    fk_id_reporte character varying
);


ALTER TABLE public.pago OWNER TO postgres;

--
-- Name: pago_id_pago_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.pago_id_pago_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.pago_id_pago_seq OWNER TO postgres;

--
-- Name: pago_id_pago_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.pago_id_pago_seq OWNED BY public.pago.id_pago;


--
-- Name: persona; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.persona (
    documento_persona character varying(20) NOT NULL,
    nombre_persona character varying(100) NOT NULL,
    edad_persona integer,
    telefono_persona character varying(20),
    fk_tipo_documento integer
);


ALTER TABLE public.persona OWNER TO postgres;

--
-- Name: propietario; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.propietario (
    id_propietario character varying(20) NOT NULL,
    email_propietario character varying(100),
    estado_propietario character varying(20)
);


ALTER TABLE public.propietario OWNER TO postgres;

--
-- Name: recolector; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.recolector (
    id_recolector character varying(20) NOT NULL,
    fechainicio_recolector date,
    fechafin_recolector date,
    estado_recolector character varying(20),
    diastrabajados_recolector integer,
    fk_id_propietario character varying,
    fk_id_finca character varying
);


ALTER TABLE public.recolector OWNER TO postgres;

--
-- Name: reporte; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.reporte (
    id_reporte character varying NOT NULL,
    fecha_reporte date NOT NULL,
    totaltecoleccion_reporte numeric(10,2),
    estado_reporte boolean,
    fk_id_recolector character varying(20)
);


ALTER TABLE public.reporte OWNER TO postgres;

--
-- Name: reporte_id_reporte_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.reporte_id_reporte_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.reporte_id_reporte_seq OWNER TO postgres;

--
-- Name: reporte_id_reporte_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.reporte_id_reporte_seq OWNED BY public.reporte.id_reporte;


--
-- Name: tipo_doc; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tipo_doc (
    id_doc integer NOT NULL,
    tipo character varying(50) NOT NULL
);


ALTER TABLE public.tipo_doc OWNER TO postgres;

--
-- Name: tipo_doc_id_doc_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tipo_doc_id_doc_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tipo_doc_id_doc_seq OWNER TO postgres;

--
-- Name: tipo_doc_id_doc_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tipo_doc_id_doc_seq OWNED BY public.tipo_doc.id_doc;


--
-- Name: usuario; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.usuario (
    id_usuario integer NOT NULL,
    username character varying NOT NULL,
    password character varying NOT NULL,
    rol character varying NOT NULL,
    fk_persona character varying
);


ALTER TABLE public.usuario OWNER TO postgres;

--
-- Name: usuario_id_usuario_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.usuario_id_usuario_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.usuario_id_usuario_seq OWNER TO postgres;

--
-- Name: usuario_id_usuario_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.usuario_id_usuario_seq OWNED BY public.usuario.id_usuario;


--
-- Name: cat_metodo_aplicacion id_metodoaplicacion; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cat_metodo_aplicacion ALTER COLUMN id_metodoaplicacion SET DEFAULT nextval('public.cat_metodo_aplicacion_id_metodoaplicacion_seq'::regclass);


--
-- Name: cat_unidad_medida id_unidadmedida; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cat_unidad_medida ALTER COLUMN id_unidadmedida SET DEFAULT nextval('public.cat_unidad_medida_id_unidadmedida_seq'::regclass);


--
-- Name: tipo_doc id_doc; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tipo_doc ALTER COLUMN id_doc SET DEFAULT nextval('public.tipo_doc_id_doc_seq'::regclass);


--
-- Name: usuario id_usuario; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.usuario ALTER COLUMN id_usuario SET DEFAULT nextval('public.usuario_id_usuario_seq'::regclass);


--
-- Data for Name: cat_metodo_aplicacion; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.cat_metodo_aplicacion (id_metodoaplicacion, nombre_metodoaplicacion) FROM stdin;
1	Bomba
\.


--
-- Data for Name: cat_tipo_insumo; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.cat_tipo_insumo (id_tipoinsumo, nombre_tipo) FROM stdin;
25665	randa
\.


--
-- Data for Name: cat_unidad_medida; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.cat_unidad_medida (id_unidadmedida, nombre_unidadmedida) FROM stdin;
3	Litros
\.


--
-- Data for Name: pago; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.pago (id_pago, fecha_pago, preciokilo_pago, estado_pago, monto_pago, metodo_pago, fk_id_reporte) FROM stdin;
\.


--
-- Data for Name: persona; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.persona (documento_persona, nombre_persona, edad_persona, telefono_persona, fk_tipo_documento) FROM stdin;
1117930622	Maria Torres	21	3138441787	1
1118020084	Andres Rodas	22	3214213545	1
40075518	cacorrin	16	3244342234	1
83056559	Moises Quesada Quintero	58	3188856827	1
1080360506	Juan Carlos Quesada Ome	21	3118260008	1
\.


--
-- Data for Name: propietario; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.propietario (id_propietario, email_propietario, estado_propietario) FROM stdin;
1117930622	mari@gmail.com	true
83056559	moisesquesadaquintero@gmail.com	true
1080360506	juancarlosquesadaome@gmail.comm	true
\.


--
-- Data for Name: recolector; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.recolector (id_recolector, fechainicio_recolector, fechafin_recolector, estado_recolector, diastrabajados_recolector, fk_id_propietario, fk_id_finca) FROM stdin;
1118020084	2026-05-01	2026-05-30	true	29	1117930622	finca_518658182f
40075518	2026-05-01	2026-05-03	true	2	1117930622	finca_518658182f
\.


--
-- Data for Name: reporte; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.reporte (id_reporte, fecha_reporte, totaltecoleccion_reporte, estado_reporte, fk_id_recolector) FROM stdin;
\.


--
-- Data for Name: tipo_doc; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.tipo_doc (id_doc, tipo) FROM stdin;
1	Cédula de Ciudadanía
2	Tarjeta de identidad
\.


--
-- Data for Name: usuario; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.usuario (id_usuario, username, password, rol, fk_persona) FROM stdin;
5	admin	admin	admin	\N
6	maria	maria	propietario	1117930622
7	moises	moises	propietario	83056559
8	juan	juan	propietario	1080360506
\.


--
-- Name: cat_metodo_aplicacion_id_metodoaplicacion_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.cat_metodo_aplicacion_id_metodoaplicacion_seq', 2, true);


--
-- Name: cat_unidad_medida_id_unidadmedida_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.cat_unidad_medida_id_unidadmedida_seq', 3, true);


--
-- Name: pago_id_pago_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.pago_id_pago_seq', 1, false);


--
-- Name: reporte_id_reporte_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.reporte_id_reporte_seq', 1, true);


--
-- Name: tipo_doc_id_doc_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tipo_doc_id_doc_seq', 2, true);


--
-- Name: usuario_id_usuario_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.usuario_id_usuario_seq', 8, true);


--
-- Name: cat_metodo_aplicacion cat_metodo_aplicacion_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cat_metodo_aplicacion
    ADD CONSTRAINT cat_metodo_aplicacion_pkey PRIMARY KEY (id_metodoaplicacion);


--
-- Name: cat_tipo_insumo cat_tipo_insumo_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cat_tipo_insumo
    ADD CONSTRAINT cat_tipo_insumo_pkey PRIMARY KEY (id_tipoinsumo);


--
-- Name: cat_unidad_medida cat_unidad_medida_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cat_unidad_medida
    ADD CONSTRAINT cat_unidad_medida_pkey PRIMARY KEY (id_unidadmedida);


--
-- Name: pago pago_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pago
    ADD CONSTRAINT pago_pkey PRIMARY KEY (id_pago);


--
-- Name: persona persona_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.persona
    ADD CONSTRAINT persona_pkey PRIMARY KEY (documento_persona);


--
-- Name: propietario propietario_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.propietario
    ADD CONSTRAINT propietario_pkey PRIMARY KEY (id_propietario);


--
-- Name: recolector recolector_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recolector
    ADD CONSTRAINT recolector_pkey PRIMARY KEY (id_recolector);


--
-- Name: reporte reporte_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reporte
    ADD CONSTRAINT reporte_pkey PRIMARY KEY (id_reporte);


--
-- Name: tipo_doc tipo_doc_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tipo_doc
    ADD CONSTRAINT tipo_doc_pkey PRIMARY KEY (id_doc);


--
-- Name: usuario usuario_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_pkey PRIMARY KEY (id_usuario);


--
-- Name: usuario usuario_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_username_key UNIQUE (username);


--
-- Name: pago pago_fk_id_reporte_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pago
    ADD CONSTRAINT pago_fk_id_reporte_fkey FOREIGN KEY (fk_id_reporte) REFERENCES public.reporte(id_reporte) ON DELETE CASCADE;


--
-- Name: persona persona_fk_tipo_documento_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.persona
    ADD CONSTRAINT persona_fk_tipo_documento_fkey FOREIGN KEY (fk_tipo_documento) REFERENCES public.tipo_doc(id_doc) ON DELETE CASCADE;


--
-- Name: recolector recolector_fk_id_propietario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recolector
    ADD CONSTRAINT recolector_fk_id_propietario_fkey FOREIGN KEY (fk_id_propietario) REFERENCES public.propietario(id_propietario);


--
-- Name: reporte reporte_fk_id_recolector_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reporte
    ADD CONSTRAINT reporte_fk_id_recolector_fkey FOREIGN KEY (fk_id_recolector) REFERENCES public.recolector(id_recolector) ON DELETE CASCADE;


--
-- Name: usuario usuario_fk_persona_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_fk_persona_fkey FOREIGN KEY (fk_persona) REFERENCES public.persona(documento_persona);


--
-- PostgreSQL database dump complete
--

\unrestrict Fc65oD2b5Vcq5DUI21TaruwADIzUUNEwQBkmW9ZJTTcIyiIv5EdUM3sni0r22p5

