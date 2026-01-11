package com.mercadez.mercadez_backend.repository;

import com.mercadez.mercadez_backend.entity.Pessoa;
import org.springframework.data.jpa.repository.JpaRepository;

public interface PessoaRepository extends JpaRepository<Pessoa, Long> {
}
