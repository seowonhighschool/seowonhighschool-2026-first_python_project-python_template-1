import streamlit as st
 
st.title(" 이민정 남편의 이름을 말하세요")
 
name = st.text_input("이름을 입력하세요")
if name:
    st.write(f"{name}틀렸다 병신아 ww")