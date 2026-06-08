package com.mercadez;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.mercadez.dto.CadastroUsuarioRequest;
import com.mercadez.dto.LoginRequest;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class UsuarioControllerTest {

    @Autowired MockMvc    mvc;
    @Autowired ObjectMapper mapper;

    @Test @Order(1)
    void cadastrarUsuario_deveRetornar201() throws Exception {
        var req = new CadastroUsuarioRequest();
        req.setNome("Carlos Teste");
        req.setEmail("carlos@teste.com");
        req.setSenha("senha123");

        mvc.perform(post("/usuarios/cadastro")
                .contentType(MediaType.APPLICATION_JSON)
                .content(mapper.writeValueAsString(req)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.email").value("carlos@teste.com"));
    }

    @Test @Order(2)
    void cadastrarUsuarioDuplicado_deveRetornar400() throws Exception {
        var req = new CadastroUsuarioRequest();
        req.setNome("Carlos Teste");
        req.setEmail("carlos@teste.com");
        req.setSenha("senha123");

        mvc.perform(post("/usuarios/cadastro")
                .contentType(MediaType.APPLICATION_JSON)
                .content(mapper.writeValueAsString(req)))
                .andExpect(status().isBadRequest());
    }

    @Test @Order(3)
    void login_deveRetornarToken() throws Exception {
        var req = new LoginRequest();
        req.setEmail("carlos@teste.com");
        req.setSenha("senha123");

        mvc.perform(post("/usuarios/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content(mapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.token").exists())
                .andExpect(jsonPath("$.tipo").value("Bearer"));
    }

    @Test @Order(4)
    void loginSenhaErrada_deveRetornar401() throws Exception {
        var req = new LoginRequest();
        req.setEmail("carlos@teste.com");
        req.setSenha("senhaErrada");

        mvc.perform(post("/usuarios/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content(mapper.writeValueAsString(req)))
                .andExpect(status().isUnauthorized());
    }
}
