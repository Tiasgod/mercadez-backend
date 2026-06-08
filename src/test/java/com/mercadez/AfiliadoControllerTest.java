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

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class AfiliadoControllerTest {

    @Autowired MockMvc     mvc;
    @Autowired ObjectMapper mapper;

    static String tokenAfiliado;

    @Test @Order(1)
    void cadastrarAfiliado_deveRetornar201() throws Exception {
        var req = new CadastroAfiliadoRequest();
        req.setNome_proprietario("João Lojista");
        req.setEmail("joao@mercado.com");
        req.setSenha("senha456");
        req.setCnpj("12.345.678/0001-90");
        req.setMercado("Mercadinho do João");

        mvc.perform(post("/afiliados")
                .contentType(MediaType.APPLICATION_JSON)
                .content(mapper.writeValueAsString(req)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.mercado").value("Mercadinho do João"));
    }

    @Test @Order(2)
    void loginAfiliado_deveRetornarToken() throws Exception {
        var req = new LoginRequest();
        req.setEmail("joao@mercado.com");
        req.setSenha("senha456");

        var result = mvc.perform(post("/afiliados/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content(mapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.token").exists())
                .andReturn();

        var body = mapper.readTree(result.getResponse().getContentAsString());
        tokenAfiliado = body.get("token").asText();
    }

    @Test @Order(3)
    void meAfiliado_comToken_deveRetornar200() throws Exception {
        mvc.perform(get("/afiliados/me")
                .header("Authorization", "Bearer " + tokenAfiliado))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.mercado").value("Mercadinho do João"));
    }

    @Test @Order(4)
    void meAfiliado_semToken_deveRetornar403() throws Exception {
        mvc.perform(get("/afiliados/me"))
                .andExpect(status().isForbidden());
    }
}
