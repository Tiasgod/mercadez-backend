package com.mercadez.mercadez_backend.service;

import com.mercadez.mercadez_backend.model.MensagemContato;
import com.mercadez.mercadez_backend.repository.MensagemContatoRepository;
import org.springframework.stereotype.Service;

@Service
public class MensagemContatoService {

    private final MensagemContatoRepository repository;

    public MensagemContatoService(MensagemContatoRepository repository) {
        this.repository = repository;
    }

    public MensagemContato salvar(MensagemContato mensagem) {
        return repository.save(mensagem);
    }
}
