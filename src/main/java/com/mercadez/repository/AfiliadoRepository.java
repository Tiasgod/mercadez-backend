package com.mercadez.repository;

import com.mercadez.model.Afiliado;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.Optional;

@Repository
public interface AfiliadoRepository extends JpaRepository<Afiliado, Long> {
    Optional<Afiliado> findByEmail(String email);
    boolean existsByEmail(String email);
    boolean existsByCnpj(String cnpj);
}
