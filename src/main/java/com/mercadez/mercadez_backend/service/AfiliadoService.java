package com.mercadez.mercadez_backend.service;

import com.mercadez.mercadez_backend.entity.Afiliado;
import com.mercadez.mercadez_backend.repository.AfiliadoRepository;
import org.springframework.stereotype.Service;

@Service
public class AfiliadoService {

    private final AfiliadoRepository repository;

    public AfiliadoService(AfiliadoRepository repository) {
        this.repository = repository;
    }

    public Afiliado salvar(Afiliado afiliado) {
        return repository.save(afiliado);
    }
}
