package com.mercadez;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.mercadez.dto.ContatoRequest;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class ContatoControllerTest {

    @Autowired MockMvc     mvc;
    @Autowired ObjectMapper mapper;

    @Test
    void enviarMensagem_deveRetornar201() throws Exception {
        var req = new ContatoRequest();
        req.setNome("Ana Silva");
        req.setEmail("ana@email.com");
        req.setMensagem("Gostaria de saber mais sobre os planos disponíveis no Mercadez.");

        mvc.perform(post("/contato")
                .contentType(MediaType.APPLICATION_JSON)
                .content(mapper.writeValueAsString(req)))
                .andExpect(status().isCreated());
    }

    @Test
    void enviarMensagem_campoVazio_deveRetornar400() throws Exception {
        var req = new ContatoRequest();
        req.setNome("");
        req.setEmail("ana@email.com");
        req.setMensagem("Mensagem curta");

        mvc.perform(post("/contato")
                .contentType(MediaType.APPLICATION_JSON)
                .content(mapper.writeValueAsString(req)))
                .andExpect(status().isBadRequest());
    }
}
