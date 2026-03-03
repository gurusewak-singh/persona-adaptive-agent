import streamlit as st
import requests
import random

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="Adsparkx Support Chat")
st.title("Adsparkx Media Customer Support")

if "session_id" not in st.session_state:
    st.session_state.session_id = random.randint(100000, 999999)
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("Session Info")
    st.write(f"**Session ID:** {st.session_state.session_id}")
    if st.button("New Session"):
        st.session_state.session_id = random.randint(100000, 999999)
        st.session_state.messages = []
        st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("meta"):
            with st.expander("Details"):
                st.json(msg["meta"])

if user_input := st.chat_input("Type your message..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                resp = requests.get(
                    f"{API_BASE}/chat/{st.session_state.session_id}",
                    params={"query": user_input},
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("escalated"):
                    agent_reply = data.get("response", "Escalated to a human agent.")
                    st.warning(agent_reply)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": agent_reply, "meta": {"escalated": True}}
                    )
                    st.stop()

                agent_reply = data.get("response", str(data))
                st.markdown(agent_reply)

                meta = {k: v for k, v in data.items() if k != "response"}
                if meta:
                    with st.expander("Details"):
                        st.json(meta)

                st.session_state.messages.append(
                    {"role": "assistant", "content": agent_reply, "meta": meta or None}
                )
            except requests.ConnectionError:
                st.error("Cannot reach the backend. Make sure FastAPI is running on port 8000.")
            except Exception as e:
                st.error(f"Error: {e}")

