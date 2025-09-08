# Phase 1 libraries
import os
import warnings
import logging
import streamlit as st

# Phase 2 libraries
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

# Phase 3 libraries
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import PyPDFLoader
from langchain.indexes import VectorstoreIndexCreator
from langchain.chains import RetrievalQA

# Disable warnings and info logs
warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.ERROR)

st.title('Ask Chatbot!')

if 'messages' not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    st.chat_message(message['role']).markdown(message['content'])

# Cached vectorstore (loads once)
@st.cache_resource(show_spinner="Indexing PDF, please wait...")
def get_vectorstore():
    pdf_name = "./ALL IN ONE DATA.pdf"
    if not os.path.exists(pdf_name):
        st.error(f"PDF file not found: {pdf_name}")
        return None

    loaders = [PyPDFLoader(pdf_name)]
    index = VectorstoreIndexCreator(
        embedding=HuggingFaceEmbeddings(model_name='all-MiniLM-L12-v2'),
        text_splitter=RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)  # ✅ bigger chunks, fewer embeddings
    ).from_loaders(loaders)
    return index.vectorstore

prompt = st.chat_input('Pass your prompt here')

if prompt:
    st.chat_message('user').markdown(prompt)
    st.session_state.messages.append({'role': 'user', 'content': prompt})

    # ✅ Fast model
    model = "llama-3.1-8b-instant"
    groq_chat = ChatGroq(
        groq_api_key=os.environ.get("GROQ_API_KEY"),
        model_name=model
    )

    try:
        vectorstore = get_vectorstore()
        if vectorstore:
            chain = RetrievalQA.from_chain_type(
                llm=groq_chat,
                chain_type='stuff',
                retriever=vectorstore.as_retriever(search_kwargs={'k': 2}),  # ✅ fewer docs to speed up
                return_source_documents=False
            )
            result = chain({"query": prompt})
            response = result["result"]

            st.chat_message('assistant').markdown(response)
            st.session_state.messages.append({'role': 'assistant', 'content': response})
    except Exception as e:
        st.error(f"Error: {str(e)}")
