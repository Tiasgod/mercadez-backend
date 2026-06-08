package com.mercadez.repository;

import com.mercadez.model.Contato;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface ContatoRepository extends JpaRepository<Contato, Long> {
    List<Contato> findByLidoFalseOrderByCriadoEmDesc();
}
