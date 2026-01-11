package com.mercadez.mercadez_backend.repository;

import com.mercadez.mercadez_backend.model.MensagemContato;
import org.springframework.data.jpa.repository.JpaRepository;

public interface MensagemContatoRepository extends JpaRepository<MensagemContato, Long> {
}
