package com.mercadez.mercadez_backend.repository;

import com.mercadez.mercadez_backend.entity.Usuario;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface UsuarioRepository extends JpaRepository<Usuario, Long> {
    // Aqui você pode criar consultas customizadas se precisar no futuro
}
