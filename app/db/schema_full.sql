PGDMP  $    	            
    {            mycyclopedia    14.9 (Homebrew)    16.0 %    V           0    0    ENCODING    ENCODING        SET client_encoding = 'UTF8';
                      false            W           0    0 
   STDSTRINGS 
   STDSTRINGS     (   SET standard_conforming_strings = 'on';
                      false            X           0    0 
   SEARCHPATH 
   SEARCHPATH     8   SELECT pg_catalog.set_config('search_path', '', false);
                      false            Y           1262    36228    mycyclopedia    DATABASE     n   CREATE DATABASE mycyclopedia WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'C';
    DROP DATABASE mycyclopedia;
                postgres    false                        2615    2200    public    SCHEMA     2   -- *not* creating schema, since initdb creates it
 2   -- *not* dropping schema, since initdb creates it
                mahouk    false            Z           0    0    SCHEMA public    ACL     Q   REVOKE USAGE ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO PUBLIC;
                   mahouk    false    5                        3079    36280 	   uuid-ossp 	   EXTENSION     ?   CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;
    DROP EXTENSION "uuid-ossp";
                   false    5            [           0    0    EXTENSION "uuid-ossp"    COMMENT     W   COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';
                        false    2            �            1259    37098    analytics_topic_history_    TABLE     �   CREATE TABLE public.analytics_topic_history_ (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    creation_timestamp timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    topic character varying NOT NULL
);
 ,   DROP TABLE public.analytics_topic_history_;
       public         heap    postgres    false    2    5    5            �            1259    36272    chat_    TABLE     �   CREATE TABLE public.chat_ (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    creation_timestamp timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    user_id bigint,
    topic character varying,
    fork_message_id uuid
);
    DROP TABLE public.chat_;
       public         heap    postgres    false    2    5    5            �            1259    36302    chat_message_    TABLE     X  CREATE TABLE public.chat_message_ (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    creation_timestamp timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    chat_id uuid NOT NULL,
    sender_id bigint,
    sender_role character varying NOT NULL,
    content_html character varying,
    content_md character varying
);
 !   DROP TABLE public.chat_message_;
       public         heap    postgres    false    2    5    5            �            1259    36379    entry_    TABLE       CREATE TABLE public.entry_ (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    creation_timestamp timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    user_id bigint,
    summary character varying,
    topic character varying NOT NULL
);
    DROP TABLE public.entry_;
       public         heap    postgres    false    2    5    5            �            1259    36399    entry_fun_fact_    TABLE     �   CREATE TABLE public.entry_fun_fact_ (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    entry_id uuid NOT NULL,
    content_md character varying NOT NULL
);
 #   DROP TABLE public.entry_fun_fact_;
       public         heap    postgres    false    2    5    5            �            1259    36412    entry_section_    TABLE     !  CREATE TABLE public.entry_section_ (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    entry_id uuid NOT NULL,
    parent_id uuid,
    index smallint NOT NULL,
    title character varying,
    content_html character varying NOT NULL,
    content_md character varying NOT NULL
);
 "   DROP TABLE public.entry_section_;
       public         heap    postgres    false    2    5    5            �            1259    36430    entry_stat_    TABLE     ;  CREATE TABLE public.entry_stat_ (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    entry_id uuid NOT NULL,
    index smallint NOT NULL,
    name_html character varying NOT NULL,
    name_md character varying NOT NULL,
    value_html character varying NOT NULL,
    value_md character varying NOT NULL
);
    DROP TABLE public.entry_stat_;
       public         heap    postgres    false    2    5    5            �            1259    36230    user_    TABLE       CREATE TABLE public.user_ (
    id bigint NOT NULL,
    email_address character varying NOT NULL,
    password character(64) NOT NULL,
    salt character(64) NOT NULL,
    name character varying,
    creation_timestamp timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);
    DROP TABLE public.user_;
       public         heap    postgres    false    5            �            1259    36229    user_id_seq    SEQUENCE     �   ALTER TABLE public.user_ ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);
            public          postgres    false    211    5            �            1259    36325    user_session_    TABLE     Y  CREATE TABLE public.user_session_ (
    id character(64) NOT NULL,
    creation_timestamp timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    user_id bigint NOT NULL,
    ip_address inet,
    mac_address macaddr,
    last_activity timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    location character varying
);
 !   DROP TABLE public.user_session_;
       public         heap    postgres    false    5            �           2606    37106 6   analytics_topic_history_ analytics_topic_history__pkey 
   CONSTRAINT     t   ALTER TABLE ONLY public.analytics_topic_history_
    ADD CONSTRAINT analytics_topic_history__pkey PRIMARY KEY (id);
 `   ALTER TABLE ONLY public.analytics_topic_history_ DROP CONSTRAINT analytics_topic_history__pkey;
       public            postgres    false    219            �           2606    36308    chat_message_ chat_message_pkey 
   CONSTRAINT     ]   ALTER TABLE ONLY public.chat_message_
    ADD CONSTRAINT chat_message_pkey PRIMARY KEY (id);
 I   ALTER TABLE ONLY public.chat_message_ DROP CONSTRAINT chat_message_pkey;
       public            postgres    false    213            �           2606    36279    chat_ chat_pkey 
   CONSTRAINT     M   ALTER TABLE ONLY public.chat_
    ADD CONSTRAINT chat_pkey PRIMARY KEY (id);
 9   ALTER TABLE ONLY public.chat_ DROP CONSTRAINT chat_pkey;
       public            postgres    false    212            �           2606    36406 #   entry_fun_fact_ entry_fun_fact_pkey 
   CONSTRAINT     a   ALTER TABLE ONLY public.entry_fun_fact_
    ADD CONSTRAINT entry_fun_fact_pkey PRIMARY KEY (id);
 M   ALTER TABLE ONLY public.entry_fun_fact_ DROP CONSTRAINT entry_fun_fact_pkey;
       public            postgres    false    216            �           2606    36387    entry_ entry_pkey 
   CONSTRAINT     O   ALTER TABLE ONLY public.entry_
    ADD CONSTRAINT entry_pkey PRIMARY KEY (id);
 ;   ALTER TABLE ONLY public.entry_ DROP CONSTRAINT entry_pkey;
       public            postgres    false    215            �           2606    36419 !   entry_section_ entry_section_pkey 
   CONSTRAINT     _   ALTER TABLE ONLY public.entry_section_
    ADD CONSTRAINT entry_section_pkey PRIMARY KEY (id);
 K   ALTER TABLE ONLY public.entry_section_ DROP CONSTRAINT entry_section_pkey;
       public            postgres    false    217            �           2606    36437    entry_stat_ entry_stat_pkey 
   CONSTRAINT     Y   ALTER TABLE ONLY public.entry_stat_
    ADD CONSTRAINT entry_stat_pkey PRIMARY KEY (id);
 E   ALTER TABLE ONLY public.entry_stat_ DROP CONSTRAINT entry_stat_pkey;
       public            postgres    false    218            �           2606    36236    user_ user__pkey 
   CONSTRAINT     N   ALTER TABLE ONLY public.user_
    ADD CONSTRAINT user__pkey PRIMARY KEY (id);
 :   ALTER TABLE ONLY public.user_ DROP CONSTRAINT user__pkey;
       public            postgres    false    211            �           2606    36331    user_session_ user_session_pkey 
   CONSTRAINT     ]   ALTER TABLE ONLY public.user_session_
    ADD CONSTRAINT user_session_pkey PRIMARY KEY (id);
 I   ALTER TABLE ONLY public.user_session_ DROP CONSTRAINT user_session_pkey;
       public            postgres    false    214            �           2606    36362    chat_ chat_fork_message_id_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.chat_
    ADD CONSTRAINT chat_fork_message_id_fkey FOREIGN KEY (fork_message_id) REFERENCES public.chat_message_(id) ON UPDATE CASCADE ON DELETE SET NULL NOT VALID;
 I   ALTER TABLE ONLY public.chat_ DROP CONSTRAINT chat_fork_message_id_fkey;
       public          postgres    false    212    213    3506            �           2606    36311 '   chat_message_ chat_message_chat_id_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.chat_message_
    ADD CONSTRAINT chat_message_chat_id_fkey FOREIGN KEY (chat_id) REFERENCES public.chat_(id) ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
 Q   ALTER TABLE ONLY public.chat_message_ DROP CONSTRAINT chat_message_chat_id_fkey;
       public          postgres    false    3504    212    213            �           2606    36316 )   chat_message_ chat_message_sender_id_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.chat_message_
    ADD CONSTRAINT chat_message_sender_id_fkey FOREIGN KEY (sender_id) REFERENCES public.user_(id) ON UPDATE CASCADE NOT VALID;
 S   ALTER TABLE ONLY public.chat_message_ DROP CONSTRAINT chat_message_sender_id_fkey;
       public          postgres    false    211    213    3502            �           2606    36297    chat_ chat_user_id_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.chat_
    ADD CONSTRAINT chat_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.user_(id) ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
 A   ALTER TABLE ONLY public.chat_ DROP CONSTRAINT chat_user_id_fkey;
       public          postgres    false    211    3502    212            �           2606    36407 ,   entry_fun_fact_ entry_fun_fact_entry_id_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.entry_fun_fact_
    ADD CONSTRAINT entry_fun_fact_entry_id_fkey FOREIGN KEY (entry_id) REFERENCES public.entry_(id) ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
 V   ALTER TABLE ONLY public.entry_fun_fact_ DROP CONSTRAINT entry_fun_fact_entry_id_fkey;
       public          postgres    false    3510    216    215            �           2606    36420 *   entry_section_ entry_section_entry_id_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.entry_section_
    ADD CONSTRAINT entry_section_entry_id_fkey FOREIGN KEY (entry_id) REFERENCES public.entry_(id) ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
 T   ALTER TABLE ONLY public.entry_section_ DROP CONSTRAINT entry_section_entry_id_fkey;
       public          postgres    false    3510    217    215            �           2606    36425 +   entry_section_ entry_section_parent_id_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.entry_section_
    ADD CONSTRAINT entry_section_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.entry_section_(id) ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
 U   ALTER TABLE ONLY public.entry_section_ DROP CONSTRAINT entry_section_parent_id_fkey;
       public          postgres    false    217    3514    217            �           2606    36438 $   entry_stat_ entry_stat_entry_id_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.entry_stat_
    ADD CONSTRAINT entry_stat_entry_id_fkey FOREIGN KEY (entry_id) REFERENCES public.entry_(id) ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
 N   ALTER TABLE ONLY public.entry_stat_ DROP CONSTRAINT entry_stat_entry_id_fkey;
       public          postgres    false    3510    215    218            �           2606    36394    entry_ entry_user_id_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.entry_
    ADD CONSTRAINT entry_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.user_(id) ON UPDATE CASCADE ON DELETE SET NULL NOT VALID;
 C   ALTER TABLE ONLY public.entry_ DROP CONSTRAINT entry_user_id_fkey;
       public          postgres    false    215    211    3502            �           2606    36340 '   user_session_ user_session_user_id_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.user_session_
    ADD CONSTRAINT user_session_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.user_(id) ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
 Q   ALTER TABLE ONLY public.user_session_ DROP CONSTRAINT user_session_user_id_fkey;
       public          postgres    false    211    3502    214           