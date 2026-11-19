from fastapi import APIRouter
from app.schemas.guide import (
    CategoryPhotoTip,
    GoldenRule,
    PhotographyGuideResponse,
)

router = APIRouter(tags=["Guia de Fotografia para Restaurantes"])


@router.get(
    "/guide",
    response_model=PhotographyGuideResponse,
    summary="Guia prático de fotografia gastronômica para vendedores de delivery",
    description=(
        "Orienta pequenos e médios restaurantes sobre como tirar fotos reais dos seus pratos "
        "com o próprio celular (iluminação, ângulo, fundo neutro) para obter resultados "
        "profissionais no pipeline do Jet Food Studio IA."
    ),
)
async def get_photography_guide() -> PhotographyGuideResponse:
    return PhotographyGuideResponse(
        title="Guia Prático de Fotografia Gastronômica — Jet Food Studio IA",
        purpose=(
            "Ajudar restaurantes e lanchonetes a substituírem fotos genéricas da internet por fotos reais, "
            "autênticas e padronizadas dos seus próprios pratos usando apenas um smartphone."
        ),
        minimum_requirements={
            "recommended_resolution": "1200x900 pixels (Proporção 4:3 — Padrão iFood)",
            "minimum_resolution": "800x600 pixels",
            "accepted_formats": ["JPEG", "PNG", "WEBP"],
            "max_file_size_mb": 10,
        },
        golden_rules=[
            GoldenRule(
                title="1. Luz Natural Lateral é o Seu Melhor Estúdio",
                description="A iluminação define 70% da aparência apetitosa de um prato.",
                do="Posicione a mesa perto de uma janela durante o dia (sem sol direto batendo no prato) para criar brilho natural nos ingredientes.",
                dont="Nunca use o flash direto do celular! Ele achata o prato, cria reflexos gordurosos e deixa as bordas escuras.",
            ),
            GoldenRule(
                title="2. Fundo Neutro e Desimpedido Facilita o Recorte por IA",
                description="Para que a IA recorte o prato com perfeição milimétrica, evite objetos colados na comida.",
                do="Apoie o prato sobre uma superfície lisa (mesa limpa, cartolina ou toalha de cor única) que contraste com a cor do prato.",
                dont="Evite fotografar com sacolas, maquininhas de cartão, mãos ou outros pratos encostados na borda do alimento principal.",
            ),
            GoldenRule(
                title="3. Limpe a Lente e Trave o Foco no Ingrediente Principal",
                description="Em cozinhas, a lente do celular acumula gordura e vapor rapidamente, deixando a foto esbranquiçada.",
                do="Passe um pano seco na lente antes de fotografar e toque na tela bem em cima do recheio principal para cravar o foco.",
                dont="Não use zoom digital (aproxime o celular fisicamente a cerca de 35cm–50cm do prato).",
            ),
            GoldenRule(
                title="4. Fotografe o Prato Recém-Montado (Frescor)",
                description="Comida perde volume e brilho poucos minutos após sair da cozinha.",
                do="Tire a foto imediatamente após finalizar o prato; pincele um fio de azeite ou água nas folhas/carnes para realçar o brilho.",
                dont="Não fotografe alimentos frios, queijos já endurecidos ou bordas de prato sujas de molho.",
            ),
        ],
        category_recommendations=[
            CategoryPhotoTip(
                category="Hambúrgueres, Sanduíches e Bolos em Camadas",
                ideal_angle="Ângulo de 30° a 45° (ou frontal na altura do lanche)",
                lighting_tip="Luz lateral frontal para iluminar as camadas de pão, carne, queijo derretido e salada.",
                staging_tip="Empurre os ingredientes levemente para a frente do pão para que o cliente veja todo o recheio.",
                recommended_preset="dark_slate",
            ),
            CategoryPhotoTip(
                category="Pizzas, Esfihas Abertas e Tábuas/Porções",
                ideal_angle="Ângulo de 90° (Zenital / Visto de cima para baixo)",
                lighting_tip="Luz difusa uniforme para não projetar a sombra do próprio celular sobre a pizza.",
                staging_tip="Destaque uma fatia levemente puxada ou distribua bem as azeitonas e folhas de manjericão no topo.",
                recommended_preset="rustic_wood",
            ),
            CategoryPhotoTip(
                category="Pratos Executivos, Marmitas, Massas e Risotos",
                ideal_angle="Ângulo de 45° (Visão natural de quem está sentado à mesa)",
                lighting_tip="Luz lateral a 45° para destacar a textura dos grãos, brilho do molho e grelhado da proteína.",
                staging_tip="Organize proteína, acompanhamento e guarnição sem empilhar um sobre o outro; limpe as bordas do prato.",
                recommended_preset="clean_studio",
            ),
            CategoryPhotoTip(
                category="Açaí, Sobremesas, Doces e Cafeteria",
                ideal_angle="Ângulo de 45° mostrando os toppings e a altura do copo/tigela",
                lighting_tip="Luz clara e suave para valorizar o brilho das frutas frescas e caldas.",
                staging_tip="Use frutas recém-cortadas no topo e deixe a calda escorrer sutilmente pela borda interna.",
                recommended_preset="warm_bistro",
            ),
        ],
        checklist_before_upload=[
            "A foto representa fielmente a porção real que o cliente vai receber em casa?",
            "O prato ou embalagem está centralizado e inteiro dentro da foto (sem cortar as laterais)?",
            "A lente da câmera foi limpa e a imagem está nítida ao dar zoom?",
            "O flash do celular estava desligado?",
            "As bordas do prato ou bancada foram limpas antes do clique?",
        ],
    )
