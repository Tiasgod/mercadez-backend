package com.mercadez.mercadez_backend.repository;

import com.mercadez.mercadez_backend.entity.Afiliado;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface AfiliadoRepository extends JpaRepository<Afiliado, Long> {

    Optional<Afiliado> findByEmailAndSenha(String email, String senha);
}
