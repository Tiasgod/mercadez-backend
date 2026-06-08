package com.mercadez;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.mercadez.dto.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class ProdutoControllerTest {

    @Autowired MockMvc     mvc;
    @Autowired ObjectMapper mapper;

    static String tokenAfiliado;
    static Long   produtoId;

    @BeforeAll
    static void setup(@Autowired MockMvc mvc, @Autowired ObjectMapper mapper) throws Exception {
        // Cadastra afiliado
        var reg = new CadastroAfiliadoRequest();
        reg.setNome_proprietario("Maria Loja");
        reg.setEmail("maria@loja.com");
        reg.setSenha("senha789");
        reg.setCnpj("98.765.432/0001-10");
        reg.setMercado("Mercado da Maria");

        mvc.perform(post("/afiliados")
                .contentType(MediaType.APPLICATION_JSON)
                .content(mapper.writeValueAsString(reg)));

        // Faz login e guarda token
        var login = new LoginRequest();
        login.setEmail("maria@loja.com");
        login.setSenha("senha789");

        var r = mvc.perform(post("/afiliados/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content(mapper.writeValueAsString(login)))
                .andReturn();

        var body = mapper.readTree(r.getResponse().getContentAsString());
        tokenAfiliado = body.get("token").asText();
    }

    @Test @Order(1)
    void listarProdutos_semLogin_deveRetornar200() throws Exception {
        mvc.perform(get("/produtos"))
                .andExpect(status().isOk());
    }

    @Test @Order(2)
    void cadastrarProduto_comToken_deveRetornar201() throws Exception {
        var req = new CadastroProdutoRequest();
        req.setNomeProduto("Arroz Camil 5kg");
        req.setTags("arroz, grãos");
        req.setPreco(new BigDecimal("22.90"));
        req.setQuantidade(100);

        var result = mvc.perform(post("/produtos")
                .header("Authorization", "Bearer " + tokenAfiliado)
                .contentType(MediaType.APPLICATION_JSON)
                .content(mapper.writeValueAsString(req)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.nomeProduto").value("Arroz Camil 5kg"))
                .andReturn();

        var body = mapper.readTree(result.getResponse().getContentAsString());
        produtoId = body.get("id").asLong();
    }

    @Test @Order(3)
    void cadastrarProduto_semToken_deveRetornar403() throws Exception {
        var req = new CadastroProdutoRequest();
        req.setNomeProduto("Feijão 1kg");
        req.setPreco(new BigDecimal("8.50"));
        req.setQuantidade(50);

        mvc.perform(post("/produtos")
                .contentType(MediaType.APPLICATION_JSON)
                .content(mapper.writeValueAsString(req)))
                .andExpect(status().isForbidden());
    }

    @Test @Order(4)
    void buscarProdutos_deveRetornarLista() throws Exception {
        mvc.perform(get("/produtos/buscar?q=arroz"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$").isArray());
    }

    @Test @Order(5)
    void atualizarProduto_comToken_deveRetornar200() throws Exception {
        var req = new CadastroProdutoRequest();
        req.setNomeProduto("Arroz Camil 5kg");
        req.setPreco(new BigDecimal("24.90"));
        req.setQuantidade(80);

        mvc.perform(put("/produtos/" + produtoId)
                .header("Authorization", "Bearer " + tokenAfiliado)
                .contentType(MediaType.APPLICATION_JSON)
                .content(mapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.preco").value(24.90));
    }

    @Test @Order(6)
    void deletarProduto_comToken_deveRetornar204() throws Exception {
        mvc.perform(delete("/produtos/" + produtoId)
                .header("Authorization", "Bearer " + tokenAfiliado))
                .andExpect(status().isNoContent());
    }
}
