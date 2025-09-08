# Phase 1 libraries
import warnings
import logging
import streamlit as st

# Phase 2 libraries
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

# Load environment variables
load_dotenv()

# Disable warnings and info logs
warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.ERROR)

st.title('Ask AKASH Chatbot!')

# Setup a session state variable to hold all the old messages
if 'messages' not in st.session_state:
    st.session_state.messages = []

# Display all the historical messages
for message in st.session_state.messages:
    st.chat_message(message['role']).markdown(message['content'])

prompt = st.chat_input('Pass your prompt here')

if prompt:
    st.chat_message('user').markdown(prompt)
    st.session_state.messages.append({'role':'user', 'content': prompt})

    # Groq system prompt
    groq_sys_prompt = ChatPromptTemplate.from_template(
        """You are very smart at everything, you always give the best,
        the most accurate and precise answers. Answer the following Question: {user_prompt}.
        Start the answer directly. No small talk please"""
    )

    # Use updated production model
    model = "llama-3.1-8b-instant"  # updated replacement

    groq_chat = ChatGroq(
        groq_api_key=os.environ.get("GROQ_API_KEY"),
        model_name=model
    )

    chain = groq_sys_prompt | groq_chat | StrOutputParser()
    response = chain.invoke({"user_prompt": prompt})

    st.chat_message('assistant').markdown(response)
    st.session_state.messages.append({'role':'assistant', 'content': response})
