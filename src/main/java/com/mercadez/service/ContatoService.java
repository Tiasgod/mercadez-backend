package com.mercadez.service;

import com.mercadez.dto.ContatoRequest;
import com.mercadez.model.Contato;
import com.mercadez.repository.ContatoRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ContatoService {

    private final ContatoRepository repo;

    public ContatoService(ContatoRepository repo) { this.repo = repo; }

    @Transactional
    public void enviar(ContatoRequest req) {
        Contato c = Contato.builder()
                .nome(req.getNome())
                .email(req.getEmail().toLowerCase())
                .mensagem(req.getMensagem())
                .build();
        repo.save(c);
    }
}
