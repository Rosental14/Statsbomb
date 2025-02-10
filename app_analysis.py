import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import seaborn as sns
from statsbombpy import sb
from mplsoccer import Sbopen, Pitch, VerticalPitch
import requests
import json
import pickle
import os

# =========================
# CONFIGURAÇÃO INICIAL
# =========================

# Carregar a lista de competições e temporadas

@st.cache_data
def carregar_competicoes():
    url_competitions = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/competitions.json"
    resp = requests.get(url_competitions)
    competitions_json = resp.json()
    return pd.DataFrame(competitions_json)

all_competitions_df = carregar_competicoes()

## Outra opção # Carregar a lista de competições e temporadas usando StatsBombpy
## all_competitions_df = sb.competitions()

# Seleciona as colunas de interesse e remove duplicatas
competitions_df = all_competitions_df[['competition_name', 'competition_id']].drop_duplicates().reset_index(drop=True)
seasons_df = all_competitions_df[['competition_name', 'season_name', 'season_id']].drop_duplicates().reset_index(drop=True)

# ===================================================================
# INTERFACE DO USUÁRIO (Sidebar) E SELEÇÃO DA COMPETIÇÃO E TEMPORADA
# ===================================================================

st.sidebar.header("Filtros para Análise de Métricas")

# Seleção de Competição (obrigatório)
competition = st.sidebar.selectbox("Selecione a Competição", competitions_df['competition_name'].unique())

# Filtra as temporadas disponíveis para a competição selecionada
filtered_seasons = seasons_df[seasons_df['competition_name'] == competition][['season_name', 'season_id']]

# Seleção da Temporada
season = st.sidebar.selectbox("Selecione a Temporada", filtered_seasons['season_name'].unique())

# Recupera os IDs correspondentes à competição e temporada selecionadas
comp_id = competitions_df.loc[competitions_df['competition_name'] == competition, 'competition_id'].iloc[0]
season_id = filtered_seasons.loc[filtered_seasons['season_name'] == season, 'season_id'].iloc[0]

# ===========================================
# EXTRAÇÃO JOGOS DA COMPETIÇÃO SELECIONADA
# ===========================================

if competition and season:
    @st.cache_data
    def carregar_jogos(comp_id, season_id):
        url_matches = f"https://raw.githubusercontent.com/statsbomb/open-data/master/data/matches/{comp_id}/{season_id}.json"
        matches = requests.get(url_matches).json()
        return pd.json_normalize(matches, sep='.')

    championship_df = carregar_jogos(comp_id, season_id)

# Correção dos nomes das colunas
championship_df.columns = championship_df.columns.str.replace("competition.", "", regex=False)
championship_df.columns = championship_df.columns.str.replace("season.", "", regex=False)
championship_df.columns = championship_df.columns.str.replace("home_team.", "", regex=False)
championship_df.columns = championship_df.columns.str.replace("away_team.", "", regex=False)

## Outra forma usando statsbombpy
## championship_df = sb.matches(competition_id=comp_id , season_id=season_id )

# ===============================================
# INTERFACE DO USUÁRIO 2ª PARTE - SELEÇÃO EQUIPE
# ===============================================

teams_list = championship_df['home_team_name'].sort_values().unique()
team_selected = st.sidebar.selectbox("Selecione a Equipe", options=teams_list)

# =========================
# INICIALIZANDO O PARSER
# =========================
    
match_df = championship_df.loc[(championship_df['home_team_name'] == f'{team_selected}')|(championship_df['away_team_name'] == f'{team_selected}')]
match_list = match_df['match_id'].unique().tolist()

@st.cache_data
def processar_eventos(match_list):
    parser = Sbopen()
    all_df = []

    for id in match_list:
        df, _, _, _ = parser.event(id)
        all_df.append(df)

    return pd.concat(all_df, ignore_index=True)

with st.spinner("Carregando eventos..."):
    df_combined = processar_eventos(match_list)

# ================================================================
# INTERFACE DO USUÁRIO 3ª PARTE - SELEÇÃO DO JOGO
# ================================================================

# Cria a lista de opções: cada item é uma tupla (match_id, "home_team vs away_team")
match_options = [(row['match_id'], f"{row['home_team_name']} vs {row['away_team_name']}") for _, row in match_df.iterrows()]
match_options = [("Todos", "Todos")] + match_options

# Cria o selectbox, de modo que o valor retornado seja a tupla completa, mas exibe somente o nome amigável
selected_option = st.sidebar.selectbox("Selecione o Jogo (opcional)", options=match_options, format_func=lambda option: option[1])

# Extrai o match_id da opção selecionada
match_selected = selected_option[0]

st.write(f"Jogo selecionado (match_id): {match_selected}")

# ================================================================
# INTERFACE DO USUÁRIO 4ª PARTE - SELEÇÃO DO JOGADOR E MÉTRICA
# ================================================================

# “Todos” indica que serão considerados todos os jogadores
df_team = df_combined[df_combined['team_name'] == team_selected]
players = df_team['player_name'].sort_values().unique()
player_selected = st.sidebar.selectbox("Selecione o Jogador (opcional)", options=["Todos"] + list(players))

# Seletor de Métrica (obrigatório)
metric = st.sidebar.selectbox("Selecione a Métrica", options=["Carry", "Dispossessed", "Dribble", "Heat_Map", "Pass", "Shot"])

# =========================
# CABEÇALHO
# =========================

st.title("Statsbomb Event Data Analysis")
st.markdown("**by Renan Rosental - Analista de Desempenho e Dados - www.linkedin.com/in/renan-rosental**")
st.write(f"Métrica: **{metric}** | Competição: **{competition}** | Temporada: **{season}** | Equipe: **{team_selected}**")
if match_selected != "Todos":
    st.write(f"Jogo selecionado: **{match_selected}**")
if player_selected != "Todos":
    st.write(f"Jogador selecionado: **{player_selected}**")

# =========================
# FUNÇÕES DE ANÁLISES
# =========================

    # =========================
    # CARRY
    # =========================

def carry_analysis(team_selected, match_selected=None, player_selected=None):
    
    df_carry = df_combined[df_combined['type_name'] == 'Carry']    
    df_carry = df_carry[df_carry['team_name'] == team_selected]
    
    if match_selected != "Todos":
        df_carry = df_carry[df_carry['match_id'] == match_selected]
        
    if player_selected != "Todos":
        df_carry = df_carry[df_carry['player_name'] == player_selected]
        
    # Resetar os índices para evitar KeyError
    df_carry = df_carry.reset_index(drop=True)
    
    if df_carry.empty:
        st.write("Nenhum dado encontrado para os filtros aplicados.")
        return

    start_x = df_carry.x
    start_y = df_carry.y
    end_x = df_carry.end_x
    end_y = df_carry.end_y

    # Condições
    condução_ofensiva = (end_x >= start_x + 5)
    condução_lateral = (end_x < start_x + 5) & (end_x > start_x - 5)
    condução_defensiva = (end_x < start_x - 5)
    
    # Definindo cores para conduções
    cores = []
    for i in range(len(start_x)):
        if condução_ofensiva[i]:
            cores.append('#008000')  # Verde 
        elif condução_lateral[i]:
            cores.append('#FFD700')  # Dourado 
        elif condução_defensiva[i]:
            cores.append('#800080')  # Roxo 
        else:
            cores.append('#FFA500')  # Laranja para outros
    
    # Campo
    pitch = Pitch(pitch_color='#aabb97', line_color='white', stripe_color='#c2d59d', stripe=True)
    fig, ax = pitch.draw(figsize=(10, 6))
    
    # Plotando as marcações
    for i in range(len(start_x)):
        pitch.lines(start_x[i], start_y[i], end_x[i], end_y[i], ax=ax, color=cores[i], comet=True)
    
    # Adicionando a legenda das cores
    legend_colors = [
        mpatches.Patch(color='#008000', label='Condução Ofensiva'),
        mpatches.Patch(color='#FFD700', label='Condução Lateral'),
        mpatches.Patch(color='#800080', label='Condução Defensiva')]
    
    legend = ax.legend(handles=legend_colors, loc='upper right', bbox_to_anchor=(1.26, 1), title="Tipos de Conduções", title_fontsize=14, fontsize=10)
    
    st.pyplot(fig)


    # =========================
    # DISPOSSESSED
    # =========================

def dispossessed_analysis(team_selected, match_selected=None, player_selected=None):
    
    df_dispossessed = df_combined[df_combined['type_name'] == 'Dispossessed']    
    df_dispossessed = df_dispossessed[df_dispossessed['team_name'] == team_selected]
    
    if match_selected != "Todos":
        df_dispossessed = df_dispossessed[df_dispossessed['match_id'] == match_selected]
        
    if player_selected != "Todos":
        df_dispossessed = df_dispossessed[df_dispossessed['player_name'] == player_selected]
        
    # Resetar os índices para evitar KeyError
    df_dispossessed = df_dispossessed.reset_index(drop=True)
    
    if df_dispossessed.empty:
        st.write("Nenhum dado encontrado para os filtros aplicados.")
        return

    pitch = Pitch(pitch_color='#aabb97', line_color='white', stripe_color='#c2d59d', stripe=True)

    # Condições
    first_third = df_dispossessed[df_dispossessed['x'] <= 40]
    second_third = df_dispossessed[(df_dispossessed['x'] > 40) & (df_dispossessed['x'] <= 80)]
    third_third = df_dispossessed[df_dispossessed['x'] > 80 ]

    # Impressão na tela
    st.write('Perdas de bola no primeiro terço:', len(first_third))
    st.write('Perdas de bola no segundo terço:', len(second_third))
    st.write('Perdas de bola no último terço:', len(third_third))

    # Definindo as cores com base no terço do campo
    cores = []
    for _, row in df_dispossessed.iterrows():
        if row['x'] <= 40:
            cores.append('#FF0000')  # Vermelho para o primeiro terço (defensivo)
        elif 40 < row['x'] <= 80:
            cores.append('#0000FF')  # Azul para o segundo terço (meio-campo)
        else:
            cores.append('#000000')  # Preto para o último terço (ofensivo)

    fig, ax = pitch.draw(figsize=(10, 6))
    scatter = pitch.scatter(df_dispossessed.x, df_dispossessed.y, ax=ax, edgecolor='black', color=cores)
    
    # Legenda
    legend_colors = [
        mpatches.Patch(color='#FF0000', label='Primeiro Terço'),
        mpatches.Patch(color='#0000FF', label='Segundo Terço'),
        mpatches.Patch(color='#000000', label='Último Terço')]

    plt.legend(
        handles=legend_colors,
        loc='upper left',
        bbox_to_anchor=(1, 1),
        title="Legenda",
        title_fontsize=14,
        fontsize=10)
    
    st.pyplot(fig)
    
    # =========================
    # DRIBBLE
    # =========================

def dribble_analysis(team_selected, match_selected=None, player_selected=None):
    
    df_dribble = df_combined[df_combined['type_name'] == 'Dribble']    
    df_dribble = df_dribble[df_dribble['team_name'] == team_selected]
    
    if match_selected != "Todos":
        df_dribble = df_dribble[df_dribble['match_id'] == match_selected]
        
    if player_selected != "Todos":
        df_dribble = df_dribble[df_dribble['player_name'] == player_selected]
        
    # Resetar os índices para evitar KeyError
    df_dribble = df_dribble.reset_index(drop=True)
    
    if df_dribble.empty:
        st.write("Nenhum dado encontrado para os filtros aplicados.")
        return

    # Campo
    pitch = Pitch(pitch_color='#aabb97', line_color='white', stripe_color='#c2d59d', stripe=True)
    
    completo = df_dribble[df_dribble['outcome_name'] == 'Complete']
    incompleto = df_dribble[df_dribble['outcome_name'] == 'Incomplete']
    
    # Impressão na tela
    st.write('Dribles Completos:', len(completo))
    st.write('Dribles Incompletos:', len(incompleto))
    
    # Definindo as cores dependendo da situação (completo ou não)
    cores = []
    for _, row in df_dribble.iterrows():
        if row['outcome_name'] == 'Complete':
            cores.append('#0000FF')  # Azul
        else:
            cores.append('#FF0000')  # Vermelho


    fig, ax = pitch.draw(figsize=(10, 6))
    scatter = pitch.scatter(df_dribble.x, df_dribble.y, ax=ax, edgecolor='black', color=cores)
    
    # Legenda de resultados do drible (outcome)
    legend_colors = [
        mpatches.Patch(color='#0000FF', label='Completo'),
        mpatches.Patch(color='#FF0000', label='Incompleto')]

    plt.legend(
        handles=legend_colors,
        loc='upper left',
        bbox_to_anchor=(1, 1),
        title="Legenda",
        title_fontsize=14,
        fontsize=10)

    st.pyplot(fig)

    # =========================
    # DUEL
    # =========================
    
    
    
    
    
    
    
    
    
    
    # =========================
    # FOULS COMMITED
    # =========================
    
    
    
    
    
    
    # =========================
    # FOULS WON
    # =========================
    
    
    
    
    
    
    
    # =========================
    # HEAT MAP
    # =========================
    
def heat_map_analysis(team_selected, match_selected=None, player_selected=None):
    
    df_heat = df_combined[~pd.isna(df_combined['x'])]   
    df_heat = df_heat[df_heat['team_name'] == team_selected]
    
    if match_selected != "Todos":
        df_heat = df_heat[df_heat['match_id'] == match_selected]
        
    if player_selected != "Todos":
        df_heat = df_heat[df_heat['player_name'] == player_selected]
        
    # Resetar os índices para evitar KeyError
    df_heat = df_heat.reset_index(drop=True)
    
    if df_heat.empty:
        st.write("Nenhum dado encontrado para os filtros aplicados.")
        return
    
    start_x = df_heat.x
    start_y = df_heat.y
    
    # Campo
    pitch = Pitch(pitch_color='#aabb97', line_color='white', stripe_color='#c2d59d', stripe=True)
    fig, ax = pitch.draw(figsize=(10, 6))
    
    pitch.kdeplot(start_x, start_y, cmap='Blues', fill=True, levels=10, alpha=0.8, ax=ax)
    
    st.pyplot(fig)
    
    # =========================
    # INTERCEPTION
    # =========================
    
    
    
    
    
    
    
    
    
    # =========================
    # MISCONTROL
    # =========================
    
    
    
    
    
    
    
    
    # =========================
    # PASS
    # =========================
    
def pass_analysis(team_selected, match_selected=None, player_selected=None):
    
    df_pass = df_combined[df_combined['type_name'] == 'Pass']    
    df_pass = df_pass[df_pass['team_name'] == team_selected]
    
    if match_selected != "Todos":
        df_pass = df_pass[df_pass['match_id'] == match_selected]
        
    if player_selected != "Todos":
        df_pass = df_pass[df_pass['player_name'] == player_selected]
        
    # Resetar os índices para evitar KeyError
    df_pass = df_pass.reset_index(drop=True)
    
    if df_pass.empty:
        st.write("Nenhum dado encontrado para os filtros aplicados.")
        return

    # Dados
    start_x = df_pass.x
    start_y = df_pass.y
    end_x = df_pass.end_x
    end_y = df_pass.end_y
    shot_assist = df_pass.pass_shot_assist
    goal_assist = df_pass.pass_goal_assist
    cross = df_pass.pass_cross
    outcome = df_pass.outcome_name
    
    # Condições para passes
    passe_ofensivo = (end_x > start_x + 7)
    passe_lateral = (end_x < start_x + 7) & (end_x > start_x - 7)
    passe_defensivo = (end_x < start_x - 7)
    
    # Impressão na tela
    st.write('Passes-Chave:', shot_assist.count())
    st.write('Assistências:', goal_assist.count())
    st.write('Cruzamento:', cross.count())
    st.write('Passes Ofensivos:', passe_ofensivo.sum())
    st.write('Passes Defensivos:', passe_defensivo.sum())
    st.write('Passes Laterais:', passe_lateral.sum())
    
    
    # Definindo cor para tipos de passes
    cores = []
    linhas_tracadas = []  # Lista para armazenar se o passe é incompleto (usar linha tracejada)
    for i in range(len(start_x)):
        if cross[i] == True:
            cores.append('#FF0000')  # Vermelho para cruzamentos
        elif goal_assist[i] == True:
            cores.append('#0000FF')  # Azul para assistências de gol
        elif shot_assist[i] == True:
            cores.append('#000000')  # Preto para assistências de chute
        elif passe_ofensivo[i]:
            cores.append('#008000')  # Verde para passes ofensivos
        elif passe_lateral[i]:
            cores.append('#FFD700')  # Dourado para passes laterais
        elif passe_defensivo[i]:
            cores.append('#800080')  # Roxo para passes defensivos
        else:
            cores.append('#FFA500')  # Laranja para outros passes
        
        # Verificar se o passe foi incompleto
        if pd.notna(outcome[i]):  # Se o outcome não for NaN, é um passe incompleto
            linhas_tracadas.append(True)
        else:
            linhas_tracadas.append(False)
    
    # Gerando o campo de jogo
    pitch = Pitch(pitch_color='#aabb97', line_color='white', stripe_color='#c2d59d', stripe=True)
    fig, ax = pitch.draw(figsize=(10, 6))
    
    # Plotando as marcações
    for i in range(len(start_x)):
        if linhas_tracadas[i]:
            # Passe incompleto: usar linha tracejada e transparência
            pitch.lines(start_x[i], start_y[i], end_x[i], end_y[i], ax=ax, color=cores[i], linestyle='--', alpha=0.3)
        else:
            # Passe completo: linha contínua estilo cometa
            pitch.lines(start_x[i], start_y[i], end_x[i], end_y[i], ax=ax, color=cores[i], comet=True, alpha=0.5)
    
    # Legenda das cores dos passes
    legend_colors = [
        mpatches.Patch(color='#000000', label='Passe-Chave'),
        mpatches.Patch(color='#0000FF', label='Assistência'),
        mpatches.Patch(color='#FF0000', label='Cruzamento'),
        mpatches.Patch(color='#008000', label='Passe Ofensivo'),
        mpatches.Patch(color='#FFD700', label='Passe Lateral'),
        mpatches.Patch(color='#800080', label='Passe Defensivo')]
    
    legend_pass_outcomes = [
        Line2D([0], [0], color='black', lw=2, linestyle='-', label='Certo'),
        Line2D([0], [0], color='black', lw=2, linestyle='--', label='Errado')]
    
    # Primeira legenda para os tipos de passes (cores)
    legend1 = ax.legend(handles=legend_colors, loc='upper right', bbox_to_anchor=(1.21, 1), title="Tipo de Passe", title_fontsize=14, fontsize=10)
    
    # Segunda legenda para status de passes (completo/incompleto)
    legend2 = ax.legend(handles=legend_pass_outcomes, loc='upper right', bbox_to_anchor=(1.21, 0.7), title="Resultado", title_fontsize=14, fontsize=10)
    
    ax.add_artist(legend1)
    
    st.pyplot(fig)
    
    # =========================
    # SHOT
    # =========================

def shot_analysis(team_selected, match_selected=None, player_selected=None):
    
    df_shot = df_combined[df_combined['type_name'] == 'Shot']    
    df_shot = df_shot[df_shot['team_name'] == team_selected]
    
    if match_selected != "Todos":
        df_shot = df_shot[df_shot['match_id'] == match_selected]
        
    if player_selected != "Todos":
        df_shot = df_shot[df_shot['player_name'] == player_selected]
        
    # Resetar os índices para evitar KeyError
    df_shot = df_shot.reset_index(drop=True)
    
    if df_shot.empty:
        st.write("Nenhum dado encontrado para os filtros aplicados.")
        return

# Dados
    start_x = df_shot.x
    start_y = df_shot.y
    body_part_name = df_shot.body_part_name
    outcome_name = df_shot.outcome_name
    xg = df_shot.shot_statsbomb_xg

    # Legenda de formas geométricas para a parte do corpo usada
    markers = []
    for part in body_part_name:
        if part == 'Right Foot':
            markers.append('s')  # Quadrado
        elif part == 'Left Foot':
            markers.append('o')  # Círculo
        elif part == 'Head':
            markers.append('^')  # Triângulo
        else:
            markers.append('D')  # Losango

    # Cores para resultado do chute (outcome)
    color_map = {
        'Goal': '#0000FF',  # Azul para gol
        'Saved': '#00FF00',  # Verde para defesa
        'Off T': '#FF0000',  # Vermelho para fora
        'Blocked': '#FFFF00',  # Amarelo para bloqueado
        'Wayward': '#FFA500',  # Laranja para desviado
        'Saved to Post': '#800080', # Roxo para trave
        'Post': '#800080'}  # Roxo para trave
    colors = [color_map[outcome] for outcome in outcome_name]

    # Tamanho com base no xG
    sizes = xg * 1000

    # Campo
    pitch = VerticalPitch(half=True, pitch_color='#aabb97', stripe_color='#c2d59d', stripe=True, line_color='white')
    fig, ax = pitch.draw(figsize=(10, 6))


    # Plot dos chutes
    for i in range(len(df_shot)):
        pitch.scatter(start_x[i], start_y[i], s=sizes[i], ax=ax, color=colors[i], marker=markers[i], edgecolor='black', alpha=0.7)

    # Legenda das partes do corpo usadas
    legend_shapes = [
        Line2D([0], [0], marker='s', color='w', label='Pé Direito', markerfacecolor='black', markersize=10),
        Line2D([0], [0], marker='o', color='w', label='Pé Esquerdo', markerfacecolor='black', markersize=10),
        Line2D([0], [0], marker='^', color='w', label='Cabeça', markerfacecolor='black', markersize=10),
        Line2D([0], [0], marker='D', color='w', label='Outro', markerfacecolor='black', markersize=10)]

    # Legenda de saídas (outcome)
    legend_colors = [
        mpatches.Patch(color='#0000FF', label='Gol'),
        mpatches.Patch(color='#00FF00', label='Defendido'),
        mpatches.Patch(color='#FF0000', label='Fora'),
        mpatches.Patch(color='#FFFF00', label='Bloqueado'),
        mpatches.Patch(color='#FFA500', label='Desviado'),
        mpatches.Patch(color='#800080', label='Trave')]

    # Legenda para o xG (escala de tamanho)
    legend_sizes = [
        Line2D([0], [0], marker='o', color='w', label='Baixo xG', markerfacecolor='gray', markersize=5),
        Line2D([0], [0], marker='o', color='w', label='Médio xG', markerfacecolor='gray', markersize=10),
        Line2D([0], [0], marker='o', color='w', label='Alto xG', markerfacecolor='gray', markersize=15)]

    plt.legend(
        handles=legend_shapes + legend_colors + legend_sizes,
        loc='upper left',
        bbox_to_anchor=(1, 1),
        title="Legenda",
        title_fontsize=14,
        fontsize=10)

    st.pyplot(fig)

# ===============================================================
# CHAMADA DA FUNÇÃO DE ANÁLISE COM BASE NA MÉTRICA SELECIONADA
# ===============================================================

if metric == "Carry":
    carry_analysis(team_selected, match_selected, player_selected)
elif metric == "Dispossessed":
    dispossessed_analysis(team_selected, match_selected, player_selected)
elif metric == "Dribble":
    dribble_analysis(team_selected, match_selected, player_selected)
elif metric == "Heat_Map":
    heat_map_analysis(team_selected, match_selected, player_selected)
elif metric == "Pass":
    pass_analysis(team_selected, match_selected, player_selected)
elif metric == "Shot":
    shot_analysis(team_selected, match_selected, player_selected)
else:
    st.write("Métrica não reconhecida. Por favor, escolha uma métrica válida.")

