package com.mercadez.mercadez_backend.controller;

import com.mercadez.mercadez_backend.entity.Afiliado;
import com.mercadez.mercadez_backend.repository.AfiliadoRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Optional;

@RestController
@RequestMapping("/login")
@CrossOrigin(origins = "*")
public class LoginController {

    @Autowired
    private AfiliadoRepository afiliadoRepository;

    @PostMapping("/afiliado")
    public Afiliado loginAfiliado(@RequestBody Afiliado dadosLogin) {

        Optional<Afiliado> afiliado = afiliadoRepository
                .findByEmailAndSenha(dadosLogin.getEmail(), dadosLogin.getSenha());

        return afiliado.orElse(null);
    }
}
