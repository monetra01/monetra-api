const API_URL = "http://127.0.0.1:8000";

let token = localStorage.getItem("monetra_token");

const botao = document.getElementById("btnNovaTransacao");

async function fazerLogin() {
    const email = prompt("Digite seu e-mail:");

    if (email === null) {
        return false;
    }

    const senha = prompt("Digite sua senha:");

    if (senha === null) {
        return false;
    }

    try {
    const resposta = await fetch(
        `${API_URL}/login?email=${encodeURIComponent(email)}&senha=${encodeURIComponent(senha)}`,
        {
            method: "POST"
        }
    );

        const resultado = await resposta.json();

        if (!resposta.ok) {
        alert(JSON.stringify(resultado.detail, null, 2));
        return false;
    }

        token = resultado.access_token;

        localStorage.setItem("monetra_token", token);

        alert("Login realizado com sucesso!");

        return true;

    } catch (erro) {
        alert("Não foi possível conectar com a API.");
        console.error(erro);
        return false;
    }
}


async function carregarSaldo() {

    if (!token) {
        return;
    }

    try {

        const resposta = await fetch(`${API_URL}/saldo`, {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        const resultado = await resposta.json();

        if (!resposta.ok) {
    alert(JSON.stringify(resultado.detail, null, 2));
    return false;
        }

        document.getElementById("saldo").textContent =
            "R$ " + Number(resultado.saldo).toFixed(2).replace(".", ",");

        document.getElementById("entradas").textContent =
            "💰 Entradas: R$ " +
            Number(resultado.total_entradas).toFixed(2).replace(".", ",");

        document.getElementById("saidas").textContent =
            "💸 Saídas: R$ " +
            Number(resultado.total_saidas).toFixed(2).replace(".", ",");

    } catch (erro) {
        console.error("Erro ao carregar saldo:", erro);
    }
}
async function carregarTransacoes() {
    if (!token) {
        return;
    }

    try {
        const resposta = await fetch(`${API_URL}/minhas-transacoes`, {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        const resultado = await resposta.json();

        if (!resposta.ok) {
            console.error("Erro ao carregar transações:", resultado);
            return;
        }

        const lista = document.getElementById("listaTransacoes");

lista.innerHTML = "";

if (resultado.length === 0) {
    lista.innerHTML = "<p>Nenhuma transação encontrada.</p>";
    return;
}

resultado.forEach(transacao => {
    const item = document.createElement("div");
          item.className = "transacao-item";

    const sinal = transacao.tipo.toLowerCase() === "entrada" ? "+" : "-";

    item.innerHTML = `
        <p>
            <strong>${transacao.descricao}</strong><br>
            ${transacao.categoria || "Sem categoria"}<br>
            ${sinal} R$ ${Number(transacao.valor).toFixed(2).replace(".", ",")}
        </p>
        <hr>
    `;

    lista.appendChild(item);
});

    } catch (erro) {
        console.error("Erro ao carregar transações:", erro);
    }
}

botao.addEventListener("click", async function () {

    if (!token) {

        const loginOK = await fazerLogin();

        if (!loginOK) {
 
           return;
        }
    
    }
    await carregarSaldo();
    await carregarTransacoes();

    const tipo = prompt(
        "Digite o tipo da transação:\n\nentrada ou saída"
    );

    if (tipo === null) {
        return;
    }

    const valorTexto = prompt("Digite o valor:");

    if (valorTexto === null) {
        return;
    }

    const valor = parseFloat(
        valorTexto.replace(",", ".")
    );

    if (isNaN(valor) || valor <= 0) {
        alert("Digite um valor válido.");
        return;
    }

    const categoria = prompt("Digite a categoria:");

    if (categoria === null) {
        return;
    }

    const descricao = prompt("Digite uma descrição:");

    if (descricao === null) {
        return;
    }

    const dados = {
        descricao: descricao,
        valor: valor,
        tipo: tipo.toLowerCase(),
        categoria: categoria
    };

    try {

        const resposta = await fetch(`${API_URL}/transacoes`, {
            method: "POST",

            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },

            body: JSON.stringify(dados)
        });

        const resultado = await resposta.json();

        if (!resposta.ok) {

            alert(
                resultado.detail ||
                "Não foi possível cadastrar a transação."
            );

            return;
        }

        alert(
            "Transação cadastrada!\n\n" +
            "Tipo: " + resultado.tipo + "\n" +
            "Valor: R$ " + Number(resultado.valor).toFixed(2).replace(".", ",") + "\n" +
            "Categoria: " + resultado.categoria
        );

        await carregarSaldo();
        await carregarTransacoes()
        await atualizarCategorias()

    } catch (erro) {

        console.error(erro);

        alert(
            "Erro ao conectar com a API.\n\n" +
            "Verifique se o servidor está funcionando."
        );
    }

});


carregarSaldo();

async function atualizarCategorias() {
    if (!token) {
        return;
    }

    try {
        const resposta = await fetch(`${API_URL}/minhas-transacoes`, {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        const transacoes = await resposta.json();

        if (!resposta.ok) {
            console.error("Erro ao carregar categorias:", transacoes);
            return;
        }

        let transporte = 0;
        let alimentacao = 0;
        let casa = 0;
        let outros = 0;

        transacoes.forEach(transacao => {

            const categoria = String(transacao.categoria || "").trim().toLowerCase();
            const valor = Number(transacao.valor);

            if (categoria === "transporte") {
                transporte += valor;
            } else if (categoria === "alimentação" || categoria === "alimentacao") {
                alimentacao += valor;
            } else if (categoria === "casa") {
                casa += valor;
            } else {
                outros += valor;
            }
        });

        document.getElementById("transporte").textContent =
            `R$ ${transporte.toFixed(2).replace(".", ",")}`;

        document.getElementById("alimentacao").textContent =
            `R$ ${alimentacao.toFixed(2).replace(".", ",")}`;

        document.getElementById("casa").textContent =
            `R$ ${casa.toFixed(2).replace(".", ",")}`;

        document.getElementById("outros").textContent =
            `R$ ${outros.toFixed(2).replace(".", ",")}`;

    } catch (erro) {
        console.error("Erro ao atualizar categorias:", erro);
    }
}
atualizarCategorias()
