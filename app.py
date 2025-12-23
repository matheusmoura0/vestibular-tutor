import streamlit as st
import pdfplumber
import re
import google.generativeai as genai

# Configuração da página
st.set_page_config(page_title="Vestibular AI - Univesp Mode", layout="wide")

# --- FUNÇÕES AVANÇADAS DE EXTRAÇÃO ---

def extract_text_from_columns(page):
    """
    Função inteligente que divide a página da Univesp em duas colunas
    para evitar misturar a Questão 1 com a Questão 4.
    """
    width = page.width
    height = page.height
    
    # Definição das margens para ignorar cabeçalho e rodapé (ajuste fino)
    # Cortamos os 10% superiores e inferiores da página
    top_margin = height * 0.10
    bottom_margin = height * 0.90
    
    # Definir as caixas das colunas (Esquerda e Direita)
    # Box = (x0, top, x1, bottom)
    left_column_box = (0, top_margin, width / 2, bottom_margin)
    right_column_box = (width / 2, top_margin, width, bottom_margin)
    
    # Extrair texto de cada lado
    left_text = page.crop(left_column_box).extract_text() or ""
    right_text = page.crop(right_column_box).extract_text() or ""
    
    return left_text + "\n" + right_text

def clean_text(text):
    """Remove sujeiras comuns de provas como a da Vunesp/Univesp."""
    # Remove frases de segurança que aparecem no meio da prova
    junk_phrases = [
        "Confidencial até o momento da aplicação",
        "UVSP2404",
        "Rascunho",
        "PrObjetiva",
        "Redação"
    ]
    for junk in junk_phrases:
        text = text.replace(junk, "")
    return text

def extract_questions_advanced(pdf_file):
    full_text = ""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                # Pula a capa (normalmente página 1) se necessário, ou processa tudo
                extracted = extract_text_from_columns(page)
                full_text += extracted + "\n"
    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")
        return {}

    full_text = clean_text(full_text)

    # NOVO REGEX: Procura especificamente por "QUESTÃO 01", "QUESTÃO 10", etc.
    # O padrão pega a palavra QUESTÃO, espaços opcionais, e o número.
    pattern = r'(?:QUESTÃO\s+)(\d+)'
    
    # O split vai separar o texto mantendo o número da questão como delimitador
    parts = re.split(pattern, full_text)
    
    questions = {}
    
    if len(parts) > 1:
        # A lista parts fica assim: [Lixo, "01", "Texto da Q1...", "02", "Texto da Q2..."]
        # Começamos do índice 1
        for i in range(1, len(parts), 2):
            q_num = parts[i]
            # Removemos o zero à esquerda para ficar padrão (ex: "01" vira "1")
            q_key = str(int(q_num)) 
            
            if i + 1 < len(parts):
                q_text = parts[i+1].strip()
                questions[q_key] = q_text
            
    return questions

def ask_gemini(api_key, question, answer):
    if not api_key:
        return "⚠️ Configure sua API Key primeiro."
        
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        Você é um tutor de vestibular.
        Resolva a seguinte questão da UNIVESP passo a passo.
        
        Questão: {question}
        
        {'O Gabarito oficial é: ' + answer if answer else ''}
        
        Explique de forma clara, focada no aprendizado.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erro na IA: {e}"

# --- INTERFACE ---

st.title("🎓 Vestibular Tutor - Vunesp Mode")
st.markdown("Otimizado para provas com duas colunas (Univesp, Unesp, etc).")

with st.sidebar:
    api_key = st.text_input("Gemini API Key", type="password")

col1, col2 = st.columns(2)
with col1:
    pdf_file = st.file_uploader("Upload da Prova (PDF)", type="pdf")
with col2:
    gabarito_txt = st.text_area("Gabarito (Ex: 1.A 2.B)", height=100)

if pdf_file:
    # Chama a nova função de extração avançada
    questions = extract_questions_advanced(pdf_file)
    
    if not questions:
        st.warning("Não encontrei questões. Verifique se o PDF não é uma imagem (escaneado).")
    else:
        # Lógica de Gabarito Simples
        answers = {}
        if gabarito_txt:
            matches = re.findall(r'(\d+)[\.\-\s]+([A-Ea-e])', gabarito_txt)
            for num, letter in matches:
                answers[str(int(num))] = letter.upper()

        # Navegação
        if 'q_idx' not in st.session_state:
            st.session_state.q_idx = 0
            
        q_numbers = sorted(questions.keys(), key=lambda x: int(x))
        
        # Proteção contra índice inválido
        if st.session_state.q_idx >= len(q_numbers):
            st.session_state.q_idx = 0
            
        current_num = q_numbers[st.session_state.q_idx]
        current_text = questions[current_num]
        
        st.divider()
        st.subheader(f"Questão {current_num}")
        
        st.info(current_text)
        
        c1, c2 = st.columns(2)
        with c1:
            with st.expander("Ver Resposta"):
                st.write(f"**{answers.get(current_num, 'Não informado')}**")
        with c2:
            if st.button("Explicar Questão"):
                with st.spinner("Analisando..."):
                    expl = ask_gemini(api_key, current_text, answers.get(current_num))
                    st.markdown(expl)
                    
        # Controles
        st.divider()
        cb1, cb2, cb3 = st.columns([1, 2, 1])
        if cb1.button("⬅️ Anterior") and st.session_state.q_idx > 0:
            st.session_state.q_idx -= 1
            st.rerun()
            
        if cb3.button("Próxima ➡️") and st.session_state.q_idx < len(q_numbers) - 1:
            st.session_state.q_idx += 1
            st.rerun()